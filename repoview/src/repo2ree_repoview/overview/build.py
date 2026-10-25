"""Build the repository overview: one static page over what the repository already knows.

It draws nothing new from the code. It reads the zones and the behaviour
specification as their owners export them, the gates' receipts, the coverage
and excuses of the last assurance-gate receipt, the operations traceview folds from
that receipt's verifications, the generated architecture and recipe
diagrams, the Just recipes, the environment contract, and the OpenAPI contract,
and lays them out page by page.

The overview is a bundle bound to one commit: whatever it shows from outside the tree
(test evidence, diagrams) is copied into it, and what is too large to copy (REE Git
archives, spans) is listed by sha256. manifest.json records the commit, whether the
working tree was dirty, and every input. `just repo-overview` regenerates the diagrams
and writes reports/overview/<revision>/, with reports/overview/latest pointing at it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo2ree_repoview.diagrams.recipes import load_recipes
from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.overview.contracts import Environment, OpenApi
from repo2ree_repoview.overview.exports import (
    SPEC_EXPORT,
    ZONES_EXPORT,
    Operations,
    Spec,
    Zones,
    exported,
    operations_export,
    shown,
)
from repo2ree_repoview.overview.html import Page, esc
from repo2ree_repoview.overview.pages.api import page_api
from repo2ree_repoview.overview.pages.architecture import page_architecture
from repo2ree_repoview.overview.pages.configuration import page_configuration
from repo2ree_repoview.overview.pages.coverage import page_coverage
from repo2ree_repoview.overview.pages.gates import page_gates
from repo2ree_repoview.overview.pages.home import page_home
from repo2ree_repoview.overview.pages.operations import page_operations
from repo2ree_repoview.overview.pages.recipes import page_recipes
from repo2ree_repoview.overview.pages.specification import page_specification
from repo2ree_repoview.overview.pages.vocabulary import page_vocabulary
from repo2ree_repoview.overview.pages.zones import page_zones
from repo2ree_repoview.overview.receipt import (
    Exercised,
    bundle_evidence,
    decisions,
    read_receipt,
    receipt_states,
    unreached,
)
from repo2ree_repoview.repository import ROOT, Head

OVERVIEWS = ROOT / "reports/overview"

# The page's look and its filter boxes, inlined so the page is one file.
STYLE = (Path(__file__).with_name("overview.css")).read_text()
SCRIPT = (Path(__file__).with_name("overview.js")).read_text()


def frame(page: Page, pages: list[Page], now: Head) -> str:
    """One page of the overview, with the sidebar that links them all."""
    links = "".join(
        f'<a href="{p.slug}.html"{' class="current"' if p.slug == page.slug else ""}>{p.title}</a>' for p in pages
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(page.title)} · repo2ree overview</title><style>{STYLE}</style></head>"
        f'<body><div class="layout"><nav><h1><a href="index.html">repo2ree</a></h1>'
        f'<div class="sub">overview at <code>{now.revision[:8]}</code></div>{links}</nav>'
        f"<main>{page.body}</main></div><script>{SCRIPT}</script></body></html>"
    )


def bundle_name(now: Head) -> str:
    """The folder an overview of this tree goes to: its commit, marked when the tree differs from it."""
    return now.revision[:12] + ("-dirty" if now.dirty else "")


def kept(bundle: Bundle, target: str, command: tuple[str, ...], kind: str) -> str:
    """An owner's export, kept in the bundle as the overview read it."""
    document = exported(command)
    bundle.write(target, document, shown(command), Origin(kind=kind))
    return document


def build(output: Path | None) -> Path:
    now = Head.now()
    bundle = Bundle(output or OVERVIEWS / bundle_name(now), now.revision)
    zones = Zones.model_validate_json(kept(bundle, "inputs/zones.json", ZONES_EXPORT, "zones"))
    spec = Spec.model_validate_json(kept(bundle, "inputs/spec.json", SPEC_EXPORT, "spec"))
    receipt = read_receipt()
    evidence = bundle_evidence(bundle, receipt)
    operations_document = kept(
        bundle, "inputs/operations.json", operations_export(evidence.verifications), "operations"
    )
    operations = Operations.model_validate_json(operations_document)
    excused = unreached()
    pages = [
        page_zones(zones),
        page_gates(receipt, excused, bundle, evidence),
        page_operations(operations, receipt, bundle, evidence),
        page_vocabulary(spec),
        page_specification(spec),
        page_coverage(
            spec, receipt, Exercised.over(evidence), excused, decisions(bundle, receipt, evidence), operations
        ),
        page_architecture(bundle),
        page_recipes(load_recipes(), bundle),
        page_configuration(Environment.read()),
        page_api(OpenApi.read()),
    ]
    manifest = bundle.manifest(now.provenance, receipt.revision if receipt else None)
    everything = [page_home(now, receipt_states(now, receipt), pages, zones, manifest), *pages]
    for page in everything:
        (bundle.root / f"{page.slug}.html").write_text(frame(page, everything, now), encoding="utf-8")
    (bundle.root / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if output is None:
        latest = OVERVIEWS / "latest"
        latest.unlink(missing_ok=True)
        latest.symlink_to(bundle.root.name)
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
    except FileExistsError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"open {target / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
