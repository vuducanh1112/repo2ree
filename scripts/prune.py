#!/usr/bin/env python3
"""Keep every generated tree bounded: run each owner's prune, and find what no one owns.

``scripts/generated.toml`` names the trees a checkout generates, who writes each, and the
command that keeps it bounded when it accumulates. This runs those commands, each once, then
walks the roots for whatever no entry claims: the output of something that no longer writes it.
Unclaimed paths are listed with their size and removed only with ``--remove-unclaimed``.

    python scripts/prune.py [--dry-run] [--remove-unclaimed]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "scripts" / "generated.toml"


@dataclass(frozen=True)
class Owner:
    name: str
    claims: tuple[str, ...]
    prune: tuple[str, ...] = ()


@dataclass(frozen=True)
class Registry:
    roots: tuple[str, ...]
    ignore: frozenset[str]
    owners: tuple[Owner, ...]

    @property
    def claims(self) -> dict[str, str]:
        """Each claimed path and its owner."""
        return {claim: owner.name for owner in self.owners for claim in owner.claims}


def load(path: Path = REGISTRY) -> Registry:
    document = tomllib.loads(path.read_text())
    owners = tuple(
        Owner(name, tuple(entry["claims"]), tuple(entry.get("prune", ())))
        for name, entry in document.get("owners", {}).items()
    )
    registry = Registry(tuple(document["roots"]), frozenset(document.get("ignore", ())), owners)
    if problems := registry_problems(registry):
        raise SystemExit("\n".join(f"{path}: {problem}" for problem in problems))
    return registry


def registry_problems(registry: Registry) -> list[str]:
    problems = []
    seen: dict[str, str] = {}
    for owner in registry.owners:
        for claim in owner.claims:
            if not any(Path(claim).is_relative_to(root) and claim != root for root in registry.roots):
                problems.append(f"{owner.name} claims {claim}, which lies under no root")
            if claim in seen:
                problems.append(f"{claim} is claimed by both {seen[claim]} and {owner.name}")
            seen[claim] = owner.name
    problems.extend(
        f"{claim} lies inside {other}: claim one or the other"
        for claim in seen
        for other in seen
        if claim != other and Path(claim).is_relative_to(other)
    )
    return problems


def tracked(root: Path) -> set[Path]:
    """The files git tracks under ``root``: a directory's own .gitignore is no one's output."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", str(root)], cwd=ROOT, capture_output=True, check=False
    ).stdout
    return {ROOT / name for name in listing.decode().split("\0") if name}


def unclaimed(registry: Registry, base: Path = ROOT, kept: set[Path] | None = None) -> list[Path]:
    """What lies under a root that no claim covers, as high up as it can be named.

    ``kept`` are files that are no one's output (by default the ones git tracks), never unclaimed.
    """
    claims = {base / claim for claim in registry.claims}
    found: list[Path] = []

    def walk(directory: Path, kept: set[Path]) -> None:
        for path in sorted(directory.iterdir()):
            if path.name in registry.ignore or path in claims or path in kept:
                continue
            inside = any(other.is_relative_to(path) for other in (*claims, *kept))
            if inside and path.is_dir() and not path.is_symlink():
                walk(path, kept)
            else:
                found.append(path)

    for root in registry.roots:
        directory = base / root
        if directory.is_dir():
            walk(directory, tracked(directory) if kept is None else kept)
    return found


def size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    return sum(item.lstat().st_size for item in path.rglob("*") if item.is_file() and not item.is_symlink())


def remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def run_owners(registry: Registry, *, dry_run: bool) -> list[str]:
    failed = []
    for owner in registry.owners:
        if not owner.prune:
            continue
        print(f">> {owner.name}: {' '.join(owner.prune)}{' --dry-run' if dry_run else ''}", flush=True)
        command = [sys.executable if owner.prune[0] == "python" else owner.prune[0], *owner.prune[1:]]
        if subprocess.run([*command, *(["--dry-run"] if dry_run else [])], cwd=ROOT, check=False).returncode:
            failed.append(owner.name)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="say what each owner would remove; remove nothing")
    parser.add_argument("--remove-unclaimed", action="store_true", help="also remove what no entry claims")
    args = parser.parse_args()
    registry = load()
    failed = run_owners(registry, dry_run=args.dry_run)
    stray = unclaimed(registry)
    removing = args.remove_unclaimed and not args.dry_run
    total = 0
    for path in stray:
        total += size(path)
        print(f"   {'removing' if removing else 'unclaimed'} {path.relative_to(ROOT)} ({size(path) / 2**20:.1f} MiB)")
        if removing:
            remove(path)
    if not stray:
        print(">> every generated tree is claimed")
    elif not removing:
        print(f">> {len(stray)} unclaimed ({total / 2**20:.0f} MiB): claim them in {REGISTRY.relative_to(ROOT)},")
        print(">> or remove them with `just prune --remove-unclaimed`")
    if failed:
        print(f">> prune failed for: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
