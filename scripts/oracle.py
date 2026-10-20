#!/usr/bin/env python3
"""Which parts of the repository are oracle, product, or support, as `specifications/zones.toml` declares.

- ``check [PATH...]`` refuses a change that touches the oracle and the product together:
  when one change edits the oracle and the code it judges, a rule, its reading, its
  evidence, or its excuse can be bent to fit the code, and the gate will agree with
  whatever was written. Without paths it checks what is staged, deletions and both
  sides of a rename included (the pre-commit hook). Deliberate exceptions:
  ``SKIP=spec-isolation git commit ...``.
- ``show [--files ZONE|GROUP] [PATH...]`` draws the zones over the tracked files, or
  names the zone of each path given.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT / "specifications/zones.toml"
EXPECTATIONS = ROOT / "conformance/expected-verdicts.toml"
ZONES = ("oracle", "product", "support")
RULE = {
    "oracle": "humans review every change",
    "product": "the behaviour gate judges it",
    "support": "cannot change a verdict",
}


@dataclass(frozen=True)
class Entry:
    path: str
    zone: str
    group: str


@dataclass(frozen=True)
class Zones:
    entries: tuple[Entry, ...]
    summaries: dict[str, str]

    def entry(self, path: str) -> Entry | None:
        """The longest declared entry matching ``path``: a directory prefix, or the exact file."""
        matches = [
            item
            for item in self.entries
            if path == item.path or (item.path.endswith("/") and path.startswith(item.path))
        ]
        return max(matches, key=lambda item: len(item.path), default=None)

    def zone(self, path: str) -> str | None:
        found = self.entry(path)
        return found.zone if found else None


def load(path: Path = DECLARATION) -> Zones:
    declaration = tomllib.loads(path.read_text())
    if set(declaration) != set(ZONES):
        raise ValueError(f"{path}: declare exactly the zones {', '.join(ZONES)}")
    entries: list[Entry] = []
    summaries: dict[str, str] = {}
    for zone in ZONES:
        summaries[zone] = declaration[zone]["summary"]
        for group, body in declaration[zone]["groups"].items():
            summaries[f"{zone}.{group}"] = body["summary"]
            entries += [Entry(item, zone, group) for item in body["paths"]]
    repeated = [item for item, count in Counter(entry.path for entry in entries).items() if count > 1]
    if repeated:
        raise ValueError(f"{path}: declared more than once: {', '.join(repeated)}")
    return Zones(tuple(entries), summaries)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def staged() -> list[str]:
    """Every path the staged change touches; a deletion or a rename's old side changes the oracle too."""
    return [path for path in git("diff", "--cached", "--name-only", "--no-renames", "-z").split("\0") if path]


def tracked() -> list[str]:
    """The files a commit of the working tree would hold: tracked or new, not ignored, not deleted."""
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return sorted({path for path in listed if path and (ROOT / path).is_file()})


def conflicts(paths: Sequence[str], zones: Zones | None = None) -> tuple[list[str], list[str]]:
    """(oracle paths, product paths) when both are present, else two empty lists."""
    zones = zones or load()
    oracle = [path for path in paths if zones.zone(path) == "oracle"]
    product = [path for path in paths if zones.zone(path) == "product"]
    return (oracle, product) if oracle and product else ([], [])


def check(paths: Sequence[str]) -> int:
    oracle, product = conflicts(list(paths) or staged())
    if not oracle:
        return 0
    print("This commit changes the oracle and the product together:", file=sys.stderr)
    for path in oracle:
        print(f"  oracle   {path}", file=sys.stderr)
    for path in product:
        print(f"  product  {path}", file=sys.stderr)
    print(
        "Commit the oracle first, then the product against it (`just show-oracle` draws the zones).\n"
        "For a deliberate exception: SKIP=spec-isolation git commit ...",
        file=sys.stderr,
    )
    return 1


def coverage_problems(zones: Zones, files: Iterable[str]) -> list[str]:
    """Tracked files no entry claims, and entries that claim no tracked file."""
    files = list(files)
    unclaimed = [path for path in files if zones.entry(path) is None]
    claimed = {zones.entry(path) for path in files}
    idle = [entry.path for entry in zones.entries if entry not in claimed]
    return [f"no zone declares {path}" for path in unclaimed] + [
        f"{path} is declared but owns no tracked file" for path in idle
    ]


# ---------------------------------------------------------------------------- show

COLOURS = {"oracle": "33", "product": "36", "support": "2", "bold": "1", "dim": "2", "red": "31"}
BLOCKS = {"oracle": "█", "product": "▓", "support": "░"}


def paint(text: str, colour: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{COLOURS[colour]}m{text}\033[0m"


def lines_of(path: str) -> int:
    """Lines of text; a binary file (a NUL in its first 8 KiB) weighs nothing."""
    try:
        content = (ROOT / path).read_bytes()
    except OSError:
        return 0
    return 0 if b"\0" in content[:8192] else content.count(b"\n")


def concessions() -> list[str]:
    """What the oracle currently concedes is not proven, from the gate's excuses."""
    try:
        excuses = tomllib.loads(EXPECTATIONS.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return []
    tests = excuses.get("expected", [])
    unreached = [item for entry in excuses.get("unreached", []) for item in entry.get("items", [])]
    rules = [item for item in unreached if item.startswith("rule:")]
    return [
        f"{len(tests)} test(s) may leave verdicts open: "
        + ", ".join(entry["test"].rsplit("::", 1)[-1] for entry in tests),
        f"{len(unreached)} specified item(s) no gated test reaches, {len(rules)} of them rules",
    ]


def show(zones: Zones, files: list[str]) -> None:
    weights = {path: lines_of(path) for path in files}
    by_entry: dict[Entry, list[str]] = defaultdict(list)
    for path in files:
        found = zones.entry(path)
        if found:
            by_entry[found].append(path)
    zone_files = Counter(entry.zone for entry, paths in by_entry.items() for _ in paths)
    zone_lines = Counter(
        {
            zone: sum(weights[p] for entry, paths in by_entry.items() if entry.zone == zone for p in paths)
            for zone in ZONES
        }
    )
    total = sum(zone_lines.values()) or 1

    print(
        paint("Oracle and product", "bold")
        + paint(f"  (declared in {DECLARATION.relative_to(ROOT)}; the longest entry decides)", "dim")
    )
    print()
    width = 60
    bar = "".join(paint(BLOCKS[zone] * round(width * zone_lines[zone] / total), zone) for zone in ZONES)
    print(f"  {bar}")
    print(
        "  "
        + "   ".join(paint(f"{BLOCKS[zone]} {zone} {100 * zone_lines[zone] / total:.0f}%", zone) for zone in ZONES)
        + paint("  of text lines", "dim")
    )
    print()
    for zone in ZONES:
        header = f"{zone.upper():<8} {zones.summaries[zone]}"
        print(paint(header, zone) + paint(f"  {zone_files[zone]} files, {zone_lines[zone]:,} lines", "dim"))
        groups: dict[str, list[Entry]] = defaultdict(list)
        for entry in zones.entries:
            if entry.zone == zone:
                groups[entry.group].append(entry)
        for group, entries in groups.items():
            print(f"  {paint(f'{group:<14}', 'bold')} {paint(zones.summaries[f'{zone}.{group}'], 'dim')}")
            for entry in entries:
                owned = by_entry.get(entry, [])
                noun = "file " if len(owned) == 1 else "files"
                size = f"{len(owned):>4} {noun} {sum(weights[p] for p in owned):>8,} lines"
                print(f"      {paint(f'{entry.path:<52}', zone)} {paint(size, 'dim')}")
        print()

    mixed = mixed_directories(zones, files)
    if mixed:
        print(paint("Directories that hold more than one zone", "bold"))
        for directory, parts in mixed.items():
            pieces = "  ".join(paint(f"{BLOCKS[zone]} {zone} {count}", zone) for zone, count in parts.items())
            print(f"  {directory:<16} {pieces}")
        print()

    conceded = concessions()
    if conceded:
        print(
            paint("What the oracle concedes is not proven", "bold")
            + paint(f"  ({EXPECTATIONS.relative_to(ROOT)})", "dim")
        )
        for line in conceded:
            print(f"  {line}")
        print()

    problems = coverage_problems(zones, files)
    for problem in problems:
        print(paint(f"  ! {problem}", "red"))
    print(paint("A commit may change the oracle or the product, never both; support mixes with either.", "dim"))


def mixed_directories(zones: Zones, files: list[str]) -> dict[str, Counter[str]]:
    parts: dict[str, Counter[str]] = defaultdict(Counter)
    for path in files:
        if "/" in path:
            parts[path.split("/", 1)[0] + "/"][zones.zone(path) or "unclaimed"] += 1
    return {directory: count for directory, count in sorted(parts.items()) if len(count) > 1}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="refuse oracle and product changed together").add_argument("paths", nargs="*")
    viewer = commands.add_parser("show", help="draw the zones, or name the zone of each path")
    viewer.add_argument("--files", metavar="ZONE[.GROUP]", help="list the tracked files of a zone or group")
    viewer.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(args.paths)
    zones = load()
    if args.paths:
        for path in args.paths:
            found = zones.entry(path.removeprefix("./"))
            print(
                f"{found.zone:<8} {found.group:<14} {found.path:<48} {path}"
                if found
                else f"{'?':<8} {'':<14} {'':<48} {path}"
            )
        return 0 if all(zones.entry(path.removeprefix("./")) for path in args.paths) else 1
    files = tracked()
    if args.files:
        zone, _, group = args.files.partition(".")
        for path in files:
            found = zones.entry(path)
            if found and found.zone == zone and (not group or found.group == group):
                print(path)
        return 0
    show(zones, files)
    return 1 if coverage_problems(zones, files) else 0


if __name__ == "__main__":
    raise SystemExit(main())
