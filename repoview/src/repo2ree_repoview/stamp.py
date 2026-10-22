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
import hashlib
import html
import json
import re
import tempfile
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from repo2ree_repoview.repository import Provenance

METADATA = re.compile(r"<metadata id=\"repo2ree-provenance\">.*?</metadata>\s*", re.DOTALL)
FOOTER = re.compile(
    r'<g id="repo2ree-stamp" data-viewbox="(?P<viewbox>[^"]*)" data-height="(?P<height>[^"]*)">.*?</g>\s*', re.DOTALL
)
VIEWBOX = re.compile(r'viewBox="(?P<x>[-\d.]+) (?P<y>[-\d.]+) (?P<w>[-\d.]+) (?P<h>[-\d.]+)"')
HEIGHT = re.compile(r'\bheight="(?P<value>[\d.]+)(?P<unit>[a-z]*)"')


class Stamp(Provenance):
    """Where a generated file came from, and the recipe that generated it."""

    by: str


class Recorded(Stamp):
    """A manifest entry: the stamp, and the digest of the file as stamped."""

    sha256: str


_MANIFEST = TypeAdapter[dict[str, Recorded]](dict[str, Recorded])


def label(stamp: Stamp) -> str:
    """The footer's line: the commit first, since that is what a reader needs."""
    changes = " + uncommitted changes" if stamp.dirty else ""
    generated = stamp.generated.replace("T", " ").replace("+00:00", " UTC")
    return f"repo2ree {stamp.revision[:10]}{changes} · {generated} · {stamp.by}"


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


def stamp_svg(path: Path, stamp: Stamp) -> None:
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
    facts = json.dumps(stamp.model_dump(), sort_keys=True)
    metadata = f'<metadata id="repo2ree-provenance">{html.escape(facts)}</metadata>\n'
    footer = (
        f'<g id="repo2ree-stamp" data-viewbox="{viewbox["x"]} {viewbox["y"]} {viewbox["w"]} {viewbox["h"]}" '
        f'data-height="{old_height["value"] + old_height["unit"] if old_height else ""}">'
        f'<rect x="{x:g}" y="{y + height:g}" width="{width:g}" height="{strip:g}" fill="#f8fafc"/>'
        f'<text x="{x + width - font * 0.6:g}" y="{y + height + strip * 0.68:g}" text-anchor="end" '
        f'font-family="ui-monospace,monospace" font-size="{font:g}" fill="#475569">{html.escape(label(stamp))}</text>'
        "</g>\n"
    )
    body = svg[opening.end() :]
    closing = body.rindex("</svg>")
    path.write_text(
        svg[: opening.start()] + root + "\n" + metadata + body[:closing] + footer + body[closing:], encoding="utf-8"
    )


def read_svg_stamp(path: Path) -> Stamp | None:
    """The stamp an SVG carries, or None when it carries none this version can read."""
    found = re.search(r"<metadata id=\"repo2ree-provenance\">(.*?)</metadata>", path.read_text(encoding="utf-8"))
    if found is None:
        return None
    try:
        return Stamp.model_validate_json(html.unescape(found.group(1)))
    except ValidationError:
        return None


def record(manifest: Path, files: list[Path], stamp: Stamp) -> None:
    entries = _MANIFEST.validate_json(manifest.read_bytes()) if manifest.is_file() else {}
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries[str(path.resolve().relative_to(manifest.parent.resolve()))] = Recorded(
            **stamp.model_dump(), sha256=digest
        )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=manifest.parent, delete=False) as pending:
        pending.write(_MANIFEST.dump_json(dict(sorted(entries.items())), indent=2) + b"\n")
    Path(pending.name).replace(manifest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, required=True, help="the report folder's manifest.json")
    parser.add_argument("--by", required=True, help="the recipe that generated the files")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    stamp = Stamp(**Provenance.now().model_dump(), by=args.by)
    for path in args.files:
        if path.suffix == ".svg":
            stamp_svg(path, stamp)
    record(args.manifest, args.files, stamp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
