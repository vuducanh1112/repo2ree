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
    by: str


class Recorded(Stamp):
    sha256: str


_STAMPS = TypeAdapter[dict[str, Recorded]](dict[str, Recorded])
STAMPS = "stamps"


class StampConflictError(ValueError):
    pass


def label(stamp: Stamp) -> str:
    changes = " + uncommitted changes" if stamp.dirty else ""
    generated = stamp.generated.replace("T", " ").replace("+00:00", " UTC")
    return f"repo2ree {stamp.revision[:10]}{changes} · {generated} · {stamp.by}"


def unstamp(svg: str) -> str:
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
    found = re.search(r"<metadata id=\"repo2ree-provenance\">(.*?)</metadata>", path.read_text(encoding="utf-8"))
    if found is None:
        return None
    try:
        return Stamp.model_validate_json(html.unescape(found.group(1)))
    except ValidationError:
        return None


def _stamp_files(path: Path) -> tuple[Path, list[Path]]:
    for folder in path.resolve().parents:
        found = sorted((folder / STAMPS).glob("*.json"))
        if found:
            return folder, found
    return path.parent, []


def read_recorded_stamp(path: Path) -> Stamp | None:
    folder, found = _stamp_files(path)
    key = path.resolve().relative_to(folder).as_posix()
    entries: list[Recorded] = []
    for stamps in found:
        try:
            entry = _STAMPS.validate_json(stamps.read_bytes()).get(key)
        except (OSError, ValidationError):
            continue
        if entry is not None:
            entries.append(entry)
    if len(entries) > 1:
        raise StampConflictError(f"{key} is recorded by {', '.join(sorted(entry.by for entry in entries))}")
    if not entries or entries[0].sha256 != hashlib.sha256(path.read_bytes()).hexdigest():
        return None
    return Stamp.model_validate(entries[0].model_dump(exclude={"sha256"}))


def _kept(folder: Path, target: Path) -> dict[str, Recorded]:
    try:
        earlier = _STAMPS.validate_json(target.read_bytes())
    except (OSError, ValidationError):
        return {}
    return {
        name: entry
        for name, entry in earlier.items()
        if (folder / name).is_file() and hashlib.sha256((folder / name).read_bytes()).hexdigest() == entry.sha256
    }


def record(folder: Path, files: list[Path], stamp: Stamp, *, keep: bool = False) -> None:
    target = folder / STAMPS / f"{stamp.by}.json"
    entries = _kept(folder, target) if keep else {}
    entries |= {
        path.resolve().relative_to(folder.resolve()).as_posix(): Recorded(
            **stamp.model_dump(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for path in files
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as pending:
        pending.write(_STAMPS.dump_json(dict(sorted(entries.items())), indent=2) + b"\n")
    Path(pending.name).replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", type=Path, required=True, help="the report folder the files are in")
    parser.add_argument("--by", required=True, help="the recipe that generated the files")
    parser.add_argument(
        "--keep", action="store_true", help="keep the recipe's earlier entries for files still as it stamped them"
    )
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args()
    stamp = Stamp(**Provenance.now().model_dump(), by=args.by)
    for path in args.files:
        if path.suffix == ".svg":
            stamp_svg(path, stamp)
    if not args.files and not args.keep:
        parser.error("name the files the recipe generated")
    record(args.folder, args.files, stamp, keep=args.keep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
