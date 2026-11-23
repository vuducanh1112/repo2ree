#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = ROOT / "zones.toml"


@dataclass(frozen=True)
class Entry:
    path: str
    zone: str
    group: str
    description: str


@dataclass(frozen=True)
class Group:
    name: str
    summary: str
    entries: tuple[Entry, ...]


@dataclass(frozen=True)
class Zone:
    name: str
    summary: str
    protected: bool
    groups: tuple[Group, ...]


@dataclass(frozen=True)
class Zones:
    zones: tuple[Zone, ...]

    @property
    def entries(self) -> list[Entry]:
        return [entry for zone in self.zones for group in zone.groups for entry in group.entries]

    def entry(self, path: str) -> Entry | None:
        matches = [
            item
            for item in self.entries
            if path == item.path or (item.path.endswith("/") and path.startswith(item.path))
        ]
        return max(matches, key=lambda item: len(item.path), default=None)

    def zone(self, name: str) -> Zone:
        return next(zone for zone in self.zones if zone.name == name)

    def protected(self, path: str) -> bool:
        found = self.entry(path)
        return found is not None and self.zone(found.zone).protected


def load(path: Path = DECLARATION) -> Zones:
    declaration = tomllib.loads(path.read_text())
    zones = []
    for name, body in declaration.items():
        unknown = set(body) - {"summary", "protected", "groups"}
        if unknown or not str(body.get("summary", "")).strip():
            raise ValueError(f"{path}: zone {name} needs a summary, and only protected and groups besides")
        groups = tuple(
            Group(
                group,
                spec["summary"],
                tuple(Entry(item, name, group, description) for item, description in spec["paths"].items()),
            )
            for group, spec in body.get("groups", {}).items()
        )
        zones.append(Zone(name, body["summary"], bool(body.get("protected", False)), groups))
    declared = Zones(tuple(zones))
    repeated = [item for item, count in Counter(entry.path for entry in declared.entries).items() if count > 1]
    if repeated:
        raise ValueError(f"{path}: declared more than once: {', '.join(repeated)}")
    return declared


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def staged() -> list[str]:
    return [path for path in git("diff", "--cached", "--name-only", "--no-renames", "-z").split("\0") if path]


def tracked() -> list[str]:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
    return sorted({path for path in listed if path and (ROOT / path).is_file()})


def local_only() -> list[str]:
    listed = git("ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory").split("\0")
    return sorted({path for path in listed if path and "/" not in path.rstrip("/")})


def conflicts(paths: Sequence[str], zones: Zones | None = None) -> tuple[list[str], list[str]]:
    zones = zones or load()
    protected = [path for path in paths if zones.protected(path)]
    rest = [path for path in paths if not zones.protected(path)]
    return (protected, rest) if protected and rest else ([], [])


def check(paths: Sequence[str]) -> int:
    zones = load()
    protected, rest = conflicts(list(paths) or staged(), zones)
    if not protected:
        return 0
    print("This commit changes a protected zone and an unprotected one together:", file=sys.stderr)
    for path in protected + rest:
        found = zones.entry(path)
        print(f"  {found.zone if found else '(no zone)':<10} {path}", file=sys.stderr)
    print(
        "Commit the protected change on its own, then the rest against it.\n"
        "`python scripts/zones.py map` draws the zones.\n"
        "For a deliberate exception: SKIP=spec-isolation git commit ...",
        file=sys.stderr,
    )
    return 1


def problems(zones: Zones, files: Iterable[str]) -> list[str]:
    files = list(files)
    unclaimed = [path for path in files if zones.entry(path) is None]
    claimed = {zones.entry(path) for path in files}
    idle = [entry.path for entry in zones.entries if entry not in claimed]
    return [f"no zone claims {path}" for path in unclaimed] + [
        f"{path} is declared but no tracked file is there" for path in idle
    ]


def verify() -> int:
    found = problems(load(), tracked())
    for problem in found:
        print(problem, file=sys.stderr)
    return 1 if found else 0


FORMAT = "repo2ree-zones/1"


def export(zones: Zones, files: Iterable[str]) -> dict[str, object]:
    files = list(files)
    placed = {path: zones.entry(path) for path in files}
    return {
        "format": FORMAT,
        "zones": [
            {
                "name": zone.name,
                "summary": zone.summary,
                "protected": zone.protected,
                "groups": [
                    {
                        "name": group.name,
                        "summary": group.summary,
                        "entries": [{"path": entry.path, "description": entry.description} for entry in group.entries],
                    }
                    for group in zone.groups
                ],
            }
            for zone in zones.zones
        ],
        "files": [
            {"path": path, "zone": found.zone, "group": found.group, "entry": found.path}
            if found
            else {"path": path, "zone": None, "group": None, "entry": None}
            for path, found in placed.items()
        ],
        "problems": problems(zones, files),
    }


COLOURS = {"bold": "1", "dim": "2", "red": "31", "protected": "33", "zone": "36"}


def paint(text: str, colour: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{COLOURS[colour]}m{text}\033[0m"


def draw(zones: Zones, files: list[str], local: list[str]) -> None:
    width = min(56, max(len(entry.path) for entry in zones.entries)) + 2
    print(
        paint("Repository map", "bold") + paint("   [protected] humans review every change; the rest is judged", "dim")
    )
    for zone in zones.zones:
        colour = "protected" if zone.protected else "zone"
        tag = " [protected]" if zone.protected else ""
        print()
        print(paint(f"{zone.name.upper()}{tag}", colour) + "  " + zone.summary)
        for group in zone.groups:
            print(f"  {paint(group.name, 'bold')}  {paint(group.summary, 'dim')}")
            for entry in group.entries:
                path = entry.path if len(entry.path) <= width - 2 else "…" + entry.path[-(width - 3) :]
                print(f"    {paint(f'{path:<{width}}', colour)}{entry.description}")
    if local:
        print()
        print(paint("LOCAL ONLY", "dim") + "  " + paint("ignored by git: caches, builds, test artifacts", "dim"))
        print("    " + paint("  ".join(local), "dim"))
    found = problems(zones, files)
    if found:
        print()
        for problem in found:
            print(paint(f"  ! {problem}", "red"))


def place(zones: Zones, path: str) -> str:
    found = zones.entry(path.removeprefix("./"))
    if found is None:
        return f"{path}: no zone claims it"
    zone = zones.zone(found.zone)
    tag = " [protected]" if zone.protected else ""
    return f"{path}\n  {zone.name}{tag} / {found.group}\n  {found.path}  {found.description}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="refuse protected and unprotected changes together").add_argument(
        "paths", nargs="*"
    )
    commands.add_parser("map", help="draw the repository by zone, or place each path").add_argument("paths", nargs="*")
    commands.add_parser("verify", help="report unclaimed files and entries that claim nothing")
    commands.add_parser("export", help="print the zones and where each tracked file belongs, as JSON")
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(args.paths)
    if args.command == "verify":
        return verify()
    zones = load()
    if args.command == "export":
        print(json.dumps(export(zones, tracked()), indent=2))
        return 0
    if args.paths:
        print("\n".join(place(zones, path) for path in args.paths))
        return 0 if all(zones.entry(path.removeprefix("./")) for path in args.paths) else 1
    draw(zones, tracked(), local_only())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
