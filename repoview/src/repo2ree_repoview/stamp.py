"""Record the commit a generated report file was made from.

Each file is entered in the manifest.json of its report folder (reports/diagrams/,
reports/metrics/): the revision and tree, whether the working tree differed from
them (with a hash of the difference), when, and by which recipe. An SVG also
shows the commit in a footer strip added below the drawing, so whoever looks at it
sees where it came from, and carries the full facts in a <metadata> element for tools.

    python -m repo2ree_repoview stamp --manifest reports/diagrams/manifest.json --by generate-gui-graph FILE...
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from repo2ree_repoview.repository import ROOT

METADATA = re.compile(r"<metadata id=\"repo2ree-provenance\">.*?</metadata>\s*", re.DOTALL)
FOOTER = re.compile(
    r'<g id="repo2ree-stamp" data-viewbox="(?P<viewbox>[^"]*)" data-height="(?P<height>[^"]*)">.*?</g>\s*', re.DOTALL
)
VIEWBOX = re.compile(r'viewBox="(?P<x>[-\d.]+) (?P<y>[-\d.]+) (?P<w>[-\d.]+) (?P<h>[-\d.]+)"')
HEIGHT = re.compile(r'\bheight="(?P<value>[\d.]+)(?P<unit>[a-z]*)"')


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def provenance(recipe: str) -> dict[str, Any]:
    status = git("status", "--porcelain")
    working = git("diff", "HEAD", "--binary") + status
    return {
        "revision": git("rev-parse", "HEAD"),
        "tree": git("rev-parse", "HEAD^{tree}"),
        "dirty": bool(status),
        "working_tree_sha256": hashlib.sha256(working.encode()).hexdigest() if status else None,
        "generated": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "by": recipe,
    }


def label(facts: dict[str, Any]) -> str:
    """The footer's line: the commit first, since that is what a reader needs."""
    changes = " + uncommitted changes" if facts.get("dirty") else ""
    generated = str(facts.get("generated", "")).replace("T", " ").replace("+00:00", " UTC")
    return f"repo2ree {str(facts['revision'])[:10]}{changes} · {generated} · {facts.get('by', '')}"


def unstamp(svg: str) -> str:
    """The SVG as generated: without an earlier stamp's metadata and footer, its size restored."""
    svg = METADATA.sub("", svg)
    footer = FOOTER.search(svg)
    if footer is None:
        return svg
    svg = svg[: footer.start()] + svg[footer.end() :]
    opening = re.search(r"<svg\b[^>]*>", svg)
    if opening is None:
        return svg
    root = VIEWBOX.sub(f'viewBox="{footer["viewbox"]}"', opening.group(0), count=1)
    if footer["height"]:
        root = HEIGHT.sub(f'height="{footer["height"]}"', root, count=1)
    return svg[: opening.start()] + root + svg[opening.end() :]


def stamp_svg(path: Path, facts: dict[str, Any]) -> None:
    """Add a footer strip naming the commit below the drawing, and the facts as <metadata>; replaces a stamp."""
    svg = unstamp(path.read_text(encoding="utf-8"))
    opening = re.search(r"<svg\b[^>]*>\s*", svg)
    viewbox = VIEWBOX.search(opening.group(0)) if opening else None
    if opening is None or viewbox is None:
        raise ValueError(f"{path}: no <svg viewBox> to stamp")
    x, y, width, height = (float(viewbox[key]) for key in ("x", "y", "w", "h"))
    font = max(9.0, width * 0.011)
    strip = font * 2
    root = VIEWBOX.sub(f'viewBox="{x:g} {y:g} {width:g} {height + strip:g}"', opening.group(0), count=1)
    old_height = HEIGHT.search(root)
    if old_height:
        grown = float(old_height["value"]) * (height + strip) / height
        root = HEIGHT.sub(f'height="{grown:g}{old_height["unit"]}"', root, count=1)
    metadata = f'<metadata id="repo2ree-provenance">{html.escape(json.dumps(facts, sort_keys=True))}</metadata>\n'
    footer = (
        f'<g id="repo2ree-stamp" data-viewbox="{viewbox["x"]} {viewbox["y"]} {viewbox["w"]} {viewbox["h"]}" '
        f'data-height="{old_height["value"] + old_height["unit"] if old_height else ""}">'
        f'<rect x="{x:g}" y="{y + height:g}" width="{width:g}" height="{strip:g}" fill="#f8fafc"/>'
        f'<text x="{x + width - font * 0.6:g}" y="{y + height + strip * 0.68:g}" text-anchor="end" '
        f'font-family="ui-monospace,monospace" font-size="{font:g}" fill="#475569">{html.escape(label(facts))}</text>'
        "</g>\n"
    )
    body = svg[opening.end() :]
    closing = body.rindex("</svg>")
    path.write_text(
        svg[: opening.start()] + root + "\n" + metadata + body[:closing] + footer + body[closing:], encoding="utf-8"
    )


def read_svg_stamp(path: Path) -> dict[str, Any] | None:
    """The facts an SVG carries, or None when it was never stamped."""
    found = re.search(r"<metadata id=\"repo2ree-provenance\">(.*?)</metadata>", path.read_text(encoding="utf-8"))
    return json.loads(html.unescape(found.group(1))) if found else None


def record(manifest: Path, files: list[Path], facts: dict[str, Any]) -> None:
    entries: dict[str, Any] = json.loads(manifest.read_text()) if manifest.is_file() else {}
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries[str(path.resolve().relative_to(manifest.parent.resolve()))] = facts | {"sha256": digest}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=manifest.parent, delete=False) as pending:
        pending.write(json.dumps(dict(sorted(entries.items())), indent=2) + "\n")
    Path(pending.name).replace(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True, help="the report folder's manifest.json")
    parser.add_argument("--by", required=True, help="the recipe that generated the files")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    facts = provenance(args.by)
    for path in args.files:
        if path.suffix == ".svg":
            stamp_svg(path, facts)
    record(args.manifest, args.files, facts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
