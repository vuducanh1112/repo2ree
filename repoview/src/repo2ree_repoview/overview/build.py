"""Build the repository overview: one static page over what the repository already knows.

It draws nothing new from the code. It reads the zones (zones.toml), the gates'
certificates, the behaviour specification with the coverage and excuses of the last
behaviour receipt, the generated architecture and recipe diagrams, the Just recipes,
the environment contract, and the OpenAPI contract, and lays them out page by page.

The overview is a bundle bound to one commit: whatever it shows from outside the tree
(test evidence, diagrams) is copied into it, and what is too large to copy (REE Git
archives, spans) is listed by sha256. manifest.json records the commit, whether the
working tree was dirty, and every input. `just repo-overview` regenerates the diagrams
and writes reports/overview/<revision>/, with reports/overview/latest pointing at it.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from repo2ree_repoview.overview.exports import read_spec, read_zones
from repo2ree_repoview.overview.html import Page, esc
from repo2ree_repoview.overview.inputs import (
    ENVIRONMENT,
    OPENAPI,
    OVERVIEWS,
    SPEC_EXPORT,
    ZONES_EXPORT,
    Bundle,
    Head,
    bundle_evidence,
    certificates,
    excuses,
    exported,
    head,
    recipes,
    suite_coverage,
    suite_extras,
)
from repo2ree_repoview.overview.pages.api import page_api
from repo2ree_repoview.overview.pages.architecture import page_architecture
from repo2ree_repoview.overview.pages.configuration import page_configuration
from repo2ree_repoview.overview.pages.coverage import page_coverage
from repo2ree_repoview.overview.pages.gates import page_gates
from repo2ree_repoview.overview.pages.home import file_tree, landing, page_provenance
from repo2ree_repoview.overview.pages.recipes import page_recipes
from repo2ree_repoview.overview.pages.specification import page_specification
from repo2ree_repoview.overview.pages.vocabulary import page_vocabulary
from repo2ree_repoview.overview.pages.zones import page_zones
from repo2ree_repoview.repository import git

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


def provenance(now: Head, receipt: dict[str, Any] | None) -> dict[str, Any]:
    working = git("diff", "HEAD", "--binary") + git("status", "--porcelain")
    return {
        "revision": now.revision,
        "tree": now.tree,
        "dirty": now.dirty,
        "working_tree_sha256": hashlib.sha256(working.encode()).hexdigest() if now.dirty else None,
        "generated": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "command": "python -m repo2ree_repoview overview",
        "receipt_revision": (receipt or {}).get("revision"),
    }


def build(output: Path | None) -> Path:
    now = head()
    target = output or OVERVIEWS / bundle_name(now)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    bundle = Bundle(target, now.revision)
    zones_json, spec_json = exported(ZONES_EXPORT), exported(SPEC_EXPORT)
    bundle.write("inputs/zones.json", zones_json, "python scripts/zones.py export", kind="zones")
    bundle.write("inputs/spec.json", spec_json, "python -m repo2ree_conformance export", kind="spec")
    declared = read_zones(json.loads(zones_json))
    spec = read_spec(json.loads(spec_json))
    found, receipt = certificates(now)
    runs, tests = bundle_evidence(bundle, receipt)
    edges, rules = suite_coverage(runs)
    extras = suite_extras(runs)
    _, unreached = excuses()
    listed = recipes()
    environment = json.loads(ENVIRONMENT.read_text())["variables"]
    operations = sum(len(methods) for methods in json.loads(OPENAPI.read_text())["paths"].values())
    protected = sum(1 for e in declared.entries if declared.zone(e.zone).protected)
    coverage = (receipt or {}).get("coverage", {})
    facts = provenance(now, receipt)
    pages = [
        Page(
            "zones",
            "Zones",
            f"{len(declared.zones)} zones; {protected} protected entries humans review",
            page_zones(declared),
        ),
        Page(
            "behaviour-gate",
            "Behaviour gate",
            f"{len((receipt or {}).get('tests', []))} tests in the last receipt; "
            f"{coverage.get('reached', '?')} of {coverage.get('declared', '?')} specified items reached",
            page_gates(receipt, unreached, bundle, tests),
        ),
        Page(
            "vocabulary",
            "Vocabulary",
            f"{len(spec.entities)} entities and {len(spec.boundaries)} boundary owners record, "
            f"{sum(len(e.facts) for e in spec.entities.values())} entity facts",
            page_vocabulary(spec),
        ),
        Page(
            "specification",
            "Specification",
            f"{len(spec.entities)} state machines, "
            f"{sum(len(t) for e in spec.entities.values() for t in e.edges.values())} edges, "
            f"{len(spec.invariants)} invariants",
            page_specification(spec),
        ),
        Page(
            "coverage",
            "Coverage",
            f"How the last receipt's tests exercised the specification: "
            f"{coverage.get('reached', '?')} of {coverage.get('declared', '?')} items reached",
            page_coverage(spec, edges, rules, unreached, extras),
        ),
        Page("architecture", "Architecture", "Import graphs of the backend and the GUI", page_architecture(bundle)),
        Page(
            "just-recipes",
            "Just recipes",
            f"{sum(not r['private'] for r in listed)} public recipes",
            page_recipes(listed, bundle),
        ),
        Page("configuration", "Configuration", f"{len(environment)} environment variables", page_configuration()),
        Page("api", "API", f"{operations} operations", page_api()),
    ]
    tree = file_tree(declared)
    home = Page("index", "Overview", "", landing(now, found, pages, tree) + page_provenance(facts))
    everything = [home, *pages]
    for page in everything:
        (target / f"{page.slug}.html").write_text(frame(page, everything, now), encoding="utf-8")
    manifest = facts | {"copied": bundle.copied, "referenced": bundle.referenced}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if output is None:
        latest = OVERVIEWS / "latest"
        latest.unlink(missing_ok=True)
        latest.symlink_to(target.name)
    copied = sum((target / entry["path"]).stat().st_size for entry in bundle.copied)
    print(
        f"wrote {target} ({len(everything)} pages; {len(bundle.copied)} files copied, {copied / 1e6:.1f} MB; "
        f"{len(bundle.referenced)} referenced by hash)"
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, help="write here instead of reports/overview/<revision>/")
    target = build(parser.parse_args().output)
    print(f"open {target / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
