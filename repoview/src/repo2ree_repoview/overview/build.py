"""Build the repository overview: one static page over what the repository already knows.

It runs nothing. It reads what the recipes `just repo-overview` depends on wrote: the
zones, the behaviour specification, the operations traceview folds from the
assurance-gate receipt's verifications, which showcase runs to read, and the Just recipes
(reports/exports/), and the
generated architecture, domain, specification, and recipe diagrams (reports/diagrams/), and
the assurance-gate receipt's tests assessed and drawn again (reports/behaviour/). Beside them
it reads the gates' receipts, the coverage and excuses of the last
assurance-gate receipt, how long the recipes took (logs/just/), the environment contract,
and the OpenAPI contract, and lays them out page by page.

The overview is a bundle bound to one commit: whatever it shows from outside the tree
(test evidence, diagrams) is copied into it, and what is too large to copy (REE Git
archives, spans) is listed by sha256. manifest.json records the commit, whether the
working tree was dirty, and every input. `just repo-overview` regenerates the exports and
diagrams and writes reports/overview/<revision>/, with reports/overview/latest pointing at it, and keeps
the newest few (overview/prune.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo2ree_repoview.diagrams.recipes import read_recipes
from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.overview.contracts import Environment, OpenApi
from repo2ree_repoview.overview.exports import EXPORTS, Operations, ShowcaseRuns, Spec, Zones
from repo2ree_repoview.overview.html import FRAME, Page, esc
from repo2ree_repoview.overview.pages.aggregate import page_aggregate
from repo2ree_repoview.overview.pages.api import page_api
from repo2ree_repoview.overview.pages.architecture import page_architecture
from repo2ree_repoview.overview.pages.configuration import page_configuration
from repo2ree_repoview.overview.pages.coverage import page_coverage, page_showcase_coverage
from repo2ree_repoview.overview.pages.gates import page_gates
from repo2ree_repoview.overview.pages.home import page_home
from repo2ree_repoview.overview.pages.operations import page_operations
from repo2ree_repoview.overview.pages.receipts import page_receipts
from repo2ree_repoview.overview.pages.recipes import page_recipes
from repo2ree_repoview.overview.pages.specification import page_specification
from repo2ree_repoview.overview.pages.vocabulary import page_vocabulary
from repo2ree_repoview.overview.pages.zones import page_zones
from repo2ree_repoview.overview.prune import OVERVIEWS, prune
from repo2ree_repoview.overview.receipt import (
    AggregateMoves,
    Exercised,
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
from repo2ree_repoview.overview.timings import LOGS, read_invocations, summarize
from repo2ree_repoview.repository import ROOT, Head
from repo2ree_repoview.stamp import read_recorded_stamp

# The page's look and its filter boxes, inlined so the page is one file.
STYLE = (Path(__file__).with_name("overview.css")).read_text()
SCRIPT = (Path(__file__).with_name("overview.js")).read_text()
SHELL_SCRIPT = (Path(__file__).with_name("shell.js")).read_text()


def sidebar(pages: list[Page], now: Head, current: str | None) -> str:
    """The sidebar that links every page of the overview, ``current`` marked."""
    links = "".join(
        f'<a href="{p.slug}.html"{' class="current"' if p.slug == current else ""}>{p.title}</a>' for p in pages
    )
    return (
        f'<nav><h1><a href="index.html">repo2ree</a></h1>'
        f'<div class="sub">overview at <code>{now.revision[:8]}</code></div>{links}</nav>'
    )


def head(title: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)} · repo2ree overview</title><style>{STYLE}</style></head>"
    )


def frame(page: Page, pages: list[Page], now: Head) -> str:
    """One page of the overview, with the sidebar that links them all."""
    return (
        f'{head(page.title)}<body><div class="layout">{sidebar(pages, now, page.slug)}'
        f"<main>{page.body}</main></div><script>{SCRIPT}</script></body></html>"
    )


def shell(pages: list[Page], now: Head) -> str:
    """The frame the overview shows its bundled evidence in: the sidebar, and the page beside it.

    The page is the address after ``#`` (``evidence.html?from=coverage#evidence/…/traces/dossier.html#rule=…``),
    the overview's page it was opened from is ``from``, marked in the sidebar.
    """
    return (
        f'{head("Evidence")}<body><div class="layout shell">{sidebar(pages, now, None)}'
        '<main><p class="missing" id="missing" hidden>Nothing to show: an evidence page is opened '
        'from the <a href="assurance-gate.html">assurance gate</a>, the coverage, or the operations.</p>'
        f'<iframe id="shown" title="Evidence"></iframe></main></div><script>{SHELL_SCRIPT}</script></body></html>'
    )


def bundle_name(now: Head) -> str:
    """The folder an overview of this tree goes to: its commit, marked when the tree differs from it."""
    return now.revision[:12] + ("-dirty" if now.dirty else "")


def kept(bundle: Bundle, exports: Path, kind: str) -> str:
    """An owner's export as a recipe wrote it, kept in the bundle with the commit its stamp records."""
    source = exports / f"{kind}.json"
    stamp = read_recorded_stamp(source) if source.is_file() else None
    if bundle.copy(source, f"inputs/{kind}.json", Origin(kind=kind, revision=stamp.revision if stamp else "")) is None:
        raise FileNotFoundError(f"{source}: missing; run just repo-overview, which writes it first")
    return source.read_text(encoding="utf-8")


def build(output: Path | None, exports: Path = EXPORTS) -> Path:
    now = Head.now()
    bundle = Bundle(output or OVERVIEWS / bundle_name(now), now.revision)
    zones = Zones.model_validate_json(kept(bundle, exports, "zones"))
    spec = Spec.model_validate_json(kept(bundle, exports, "spec"))
    receipt = read_receipt()
    evidence = bundle_evidence(bundle, receipt)
    operations = Operations.model_validate_json(kept(bundle, exports, "operations"))
    recipes = read_recipes(kept(bundle, exports, "just-recipes"))
    excused = unreached()
    showcases = ShowcaseRuns.model_validate_json(kept(bundle, exports, "showcases"))
    showcase_runs = list(runs_on_disk(showcases.runs()))
    showcase_evidence = bundle_runs(bundle, showcase_runs)
    verdicts = judged_now()
    # What logs/just/ held when the overview was built, kept as the overview read it.
    timings = summarize(read_invocations())
    bundle.write(
        "inputs/timings.json", timings.model_dump_json(indent=2), str(LOGS.relative_to(ROOT)), Origin(kind="timings")
    )
    pages = [
        page_zones(zones),
        page_gates(receipt, excused, bundle, evidence, verdicts),
        page_receipts(now),
        page_operations(operations, receipt, bundle, evidence),
        page_vocabulary(spec),
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
            {
                str(run.relative_to(ROOT)) if run.is_relative_to(ROOT) else str(run): record
                for run, record in showcase_runs
            },
            verdicts,
            Exercised.over(showcase_evidence),
            decisions(bundle, run_tests(showcase_runs), showcase_evidence),
            showcase_evidence,
            bundle,
            gate_needs(now, tier_receipts()).get("showcase-gate", []),
        ),
        *(
            page_aggregate(aggregate, AggregateMoves.over(evidence, name), bundle)
            for name, aggregate in spec.aggregates.items()
        ),
        page_architecture(bundle),
        page_recipes(recipes, bundle, timings),
        page_configuration(Environment.read()),
        page_api(OpenApi.read()),
    ]
    manifest = bundle.manifest(now.provenance, receipt.revision if receipt else None)
    everything = [page_home(now, receipt_states(now, receipt), pages, zones, manifest), *pages]
    for page in everything:
        (bundle.root / f"{page.slug}.html").write_text(frame(page, everything, now), encoding="utf-8")
    (bundle.root / f"{FRAME}.html").write_text(shell(everything, now), encoding="utf-8")
    (bundle.root / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if output is None:
        latest = OVERVIEWS / "latest"
        latest.unlink(missing_ok=True)
        latest.symlink_to(bundle.root.name)
        prune(OVERVIEWS)
    copied = sum((bundle.root / entry.path).stat().st_size for entry in manifest.copied)
    print(
        f"wrote {bundle.root} ({len(everything)} pages; {len(manifest.copied)} files copied, {copied / 1e6:.1f} MB; "
        f"{len(manifest.referenced)} referenced by hash)"
    )
    return bundle.root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
