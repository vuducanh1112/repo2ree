from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo2ree_repoview.diagrams.recipes import read_recipes
from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.overview.contracts import CliSchema, Environment, OpenApi
from repo2ree_repoview.overview.exports import (
    EXPORTS,
    Contracts,
    ExerciseCase,
    Exercises,
    Operations,
    ShowcaseRuns,
    ShowcaseTest,
    Spec,
    VocabularyGraph,
    Zones,
)
from repo2ree_repoview.overview.html import FRAME, Page, esc
from repo2ree_repoview.overview.pages.aggregate import page_aggregate
from repo2ree_repoview.overview.pages.architecture import page_architecture
from repo2ree_repoview.overview.pages.contracts import CONTRACTS, page_contracts
from repo2ree_repoview.overview.pages.coverage import SHOWCASES, page_coverage, page_showcase_coverage
from repo2ree_repoview.overview.pages.environment import page_environment
from repo2ree_repoview.overview.pages.exercises import EXERCISES, page_exercise, page_exercises, session_target
from repo2ree_repoview.overview.pages.gates import page_gates
from repo2ree_repoview.overview.pages.home import page_home
from repo2ree_repoview.overview.pages.interfaces import INTERFACES, page_api, page_cli, page_interfaces
from repo2ree_repoview.overview.pages.operations import page_operations
from repo2ree_repoview.overview.pages.receipts import page_receipts
from repo2ree_repoview.overview.pages.recipes import page_recipes
from repo2ree_repoview.overview.pages.showcase_ree import authoring_test, page_showcase_ree, review_test
from repo2ree_repoview.overview.pages.specification import page_specification
from repo2ree_repoview.overview.pages.specification_core import SPECIFICATION, page_specification_core
from repo2ree_repoview.overview.pages.vocabulary import page_vocabulary
from repo2ree_repoview.overview.pages.vocabulary_graph import page_vocabulary_graph
from repo2ree_repoview.overview.pages.zones import page_zones
from repo2ree_repoview.overview.prune import OVERVIEWS, prune
from repo2ree_repoview.overview.receipt import (
    AggregateMoves,
    Exercised,
    RunRecord,
    bundle_evidence,
    bundle_runs,
    decisions,
    gate_needs,
    judged_now,
    read_receipt,
    receipt_states,
    receipt_tests,
    run_tests,
    runs_on_disk,
    tier_receipts,
    unreached,
)
from repo2ree_repoview.overview.showcase_ree import SealedRee, preserved_ree
from repo2ree_repoview.overview.showcase_review import FinalReview, preserved_review
from repo2ree_repoview.overview.timings import LOGS, read_invocations, summarize
from repo2ree_repoview.repository import ROOT, Head, file_history
from repo2ree_repoview.stamp import read_recorded_stamp

STYLE = (Path(__file__).with_name("overview.css")).read_text()
SCRIPT = (Path(__file__).with_name("overview.js")).read_text()
SHELL_SCRIPT = (Path(__file__).with_name("shell.js")).read_text()


def sidebar(pages: list[Page], now: Head, current: str | None) -> str:
    links = "".join(
        f'<a href="{p.slug}.html"{' class="current"' if p.slug == current else ""}>{p.title}</a>' for p in pages
    )
    return (
        f'<nav><h1><a href="index.html">repo2ree</a></h1>'
        f'<div class="sub">overview at <code>{now.revision[:8]}</code></div>{links}</nav>'
    )


def head(title: str, base: str = "") -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + (f'<base href="{base}">' if base else "")
        + f"<title>{esc(title)} · repo2ree overview</title><style>{STYLE}</style></head>"
    )


def frame(page: Page, pages: list[Page], now: Head, current: str | None = None) -> str:
    base = "../" * page.slug.count("/")
    return (
        f'{head(page.title, base)}<body><div class="layout">{sidebar(pages, now, current or page.slug)}'
        f"<main>{page.body}</main></div><script>{SCRIPT}</script></body></html>"
    )


def shell(pages: list[Page], now: Head) -> str:
    return (
        f'{head("Evidence")}<body><div class="layout shell">{sidebar(pages, now, None)}'
        '<main><p class="missing" id="missing" hidden>Nothing to show: an evidence page is opened '
        'from the <a href="assurance-gate.html">assurance gate</a>, the coverage, or the operations.</p>'
        f'<iframe id="shown" title="Evidence"></iframe></main></div><script>{SHELL_SCRIPT}</script></body></html>'
    )


def bundle_name(now: Head) -> str:
    return now.revision[:12] + ("-dirty" if now.dirty else "")


def kept(bundle: Bundle, exports: Path, kind: str) -> str:
    source = exports / f"{kind}.json"
    stamp = read_recorded_stamp(source) if source.is_file() else None
    if bundle.copy(source, f"inputs/{kind}.json", Origin(kind=kind, revision=stamp.revision if stamp else "")) is None:
        raise FileNotFoundError(f"{source}: missing; run just repo-overview, which writes it first")
    return source.read_text(encoding="utf-8")


def _preserved(test: ShowcaseTest | None, records: dict[str, RunRecord]) -> tuple[Path, tuple[str, ...]] | None:
    record = records.get(test.run) if test and test.run else None
    found = next((t for t in record.tests if test and t.name == test.test), None) if record else None
    if test is None or test.run is None or found is None:
        return None
    return ROOT / test.run / found.directory, found.rees


def showcase_ree_pages(showcases: ShowcaseRuns, records: dict[str, RunRecord]) -> list[Page]:
    pages = []
    for showcase in showcases.showcases:
        if showcase.kind != "showcase":
            continue
        authoring, reviewing = authoring_test(showcase), review_test(showcase)
        ree: SealedRee | None = None
        review: FinalReview | None = None
        if (sealed := _preserved(authoring, records)) is not None:
            ree = preserved_ree(*sealed)
        if (reviewed := _preserved(reviewing, records)) is not None:
            review = preserved_review(*reviewed)
        pages.append(page_showcase_ree(showcase, authoring, ree, reviewing, review))
    return pages


def _session(bundle: Bundle, case: ExerciseCase) -> bool:
    if case.replay is None:
        return False
    target = session_target(case.digest)
    return bundle.copy(ROOT / case.replay.session, target, Origin(kind="session")) is not None


def build(output: Path | None, exports: Path = EXPORTS) -> Path:
    now = Head.now()
    bundle = Bundle(output or OVERVIEWS / bundle_name(now), now.revision)
    zones = Zones.model_validate_json(kept(bundle, exports, "zones"))
    spec = Spec.model_validate_json(kept(bundle, exports, "spec"))
    registry = Contracts.model_validate_json(kept(bundle, exports, "contracts"))
    vocabulary = VocabularyGraph.model_validate_json(kept(bundle, exports, "vocabulary"))
    receipt = read_receipt()
    evidence = bundle_evidence(bundle, receipt)
    operations = Operations.model_validate_json(kept(bundle, exports, "operations"))
    recipes = read_recipes(kept(bundle, exports, "just-recipes"))
    excused = unreached()
    showcases = ShowcaseRuns.model_validate_json(kept(bundle, exports, "showcases"))
    exercises = Exercises.model_validate_json(kept(bundle, exports, "exercises"))
    showcase_runs = list(runs_on_disk(showcases.runs()))
    showcase_records = {
        str(run.relative_to(ROOT)) if run.is_relative_to(ROOT) else str(run): record for run, record in showcase_runs
    }
    showcase_evidence = bundle_runs(bundle, showcase_runs)
    verdicts = judged_now()
    timings = summarize(read_invocations())
    bundle.write(
        "inputs/timings.json", timings.model_dump_json(indent=2), str(LOGS.relative_to(ROOT)), Origin(kind="timings")
    )
    cli, api = CliSchema.read(registry), OpenApi.read(registry)
    environment = Environment.read(registry)
    pages = [
        page_zones(zones),
        page_gates(receipt, excused, bundle, evidence, verdicts),
        page_receipts(now),
        page_operations(operations, receipt, bundle, evidence),
        page_vocabulary(spec, registry),
        page_specification(spec, bundle),
        page_coverage(
            spec,
            receipt,
            Exercised.over(evidence),
            excused,
            decisions(bundle, receipt_tests(receipt), evidence),
            operations,
            bundle,
        ),
        page_showcase_coverage(
            spec,
            showcases,
            showcase_records,
            verdicts,
            Exercised.over(showcase_evidence),
            decisions(bundle, run_tests(showcase_runs), showcase_evidence),
            showcase_evidence,
            bundle,
            gate_needs(now, tier_receipts()).get("showcase-gate", []),
        ),
        page_exercises(exercises),
        *(
            page_aggregate(aggregate, AggregateMoves.over(evidence, name), bundle, registry)
            for name, aggregate in spec.aggregates.items()
        ),
        page_architecture(bundle),
        page_interfaces(cli, api),
        page_contracts(bundle, registry, environment),
        page_vocabulary_graph(vocabulary),
        page_recipes(recipes, bundle, timings),
    ]
    manifest = bundle.manifest(now.provenance, receipt.revision if receipt else None)
    everything = [page_home(now, receipt_states(now, receipt), pages, zones, manifest), *pages]
    for page in everything:
        (bundle.root / f"{page.slug}.html").write_text(frame(page, everything, now), encoding="utf-8")
    subpages = [
        *((page, SHOWCASES) for page in showcase_ree_pages(showcases, showcase_records)),
        (
            page_specification_core(spec, {source.path: file_history(source.path) for source in spec.sources}),
            SPECIFICATION,
        ),
        (page_cli(cli), INTERFACES),
        (page_api(api), INTERFACES),
        (page_environment(environment), CONTRACTS),
        *((page_exercise(case, session=_session(bundle, case)), EXERCISES) for case in exercises.cases),
    ]
    for page, parent in subpages:
        written_to = bundle.root / f"{page.slug}.html"
        written_to.parent.mkdir(parents=True, exist_ok=True)
        written_to.write_text(frame(page, everything, now, parent), encoding="utf-8")
    (bundle.root / f"{FRAME}.html").write_text(shell(everything, now), encoding="utf-8")
    (bundle.root / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if output is None:
        latest = OVERVIEWS / "latest"
        latest.unlink(missing_ok=True)
        latest.symlink_to(bundle.root.name)
        prune(OVERVIEWS)
    copied = sum((bundle.root / entry.path).stat().st_size for entry in manifest.copied)
    written = len(everything) + len(subpages)
    print(
        f"wrote {bundle.root} ({written} pages; {len(manifest.copied)} files copied, {copied / 1e6:.1f} MB; "
        f"{len(manifest.referenced)} referenced by hash)"
    )
    return bundle.root


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, help="write here instead of reports/overview/<revision>/")
    try:
        target = build(parser.parse_args().output)
    except (FileExistsError, FileNotFoundError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"open {target / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
