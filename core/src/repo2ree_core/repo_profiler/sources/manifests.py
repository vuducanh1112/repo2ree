"""Manifest scan orchestration — the declared-dependency inventory source.

The format knowledge lives in the ecosystem modules (``pypi``, ``conda``,
``oci``), each contributing ``SourceParser`` entries to the registry below;
this module only walks the workspace, dispatches files to the first matching
parser, and merges the two sides.

Lockfiles are merged into the declared rows: a declared dependency whose
identity appears in a lockfile gains ``locked_version`` / ``locked_hashes``;
lock-only entries become ``direct=False`` rows (a lockfile states the full
transitive closure, so an unmatched entry is presumed transitive).

No I/O happens outside ``scan_manifest_files``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from repo2ree_core.domain.dependency import (
    Dependency,
    DependencyInventory,
    normalize_package_name,
)

from . import conda, oci, pypi
from .base import SourceParser

# ================================================
# Registry
# ================================================

_REGISTRY: tuple[SourceParser, ...] = (*pypi.PARSERS, *conda.PARSERS, *oci.PARSERS)

if len({parser.format_id for parser in _REGISTRY}) != len(_REGISTRY):
    raise AssertionError("registry format_ids must be unique")

# Directories whose contents are never the repo's own manifests.
_SKIPPED_DIRS = frozenset({".git", ".venv", "venv", "node_modules", "__pycache__"})


# ================================================
# Entry point
# ================================================


def scan_manifest_files(repo_path: Path) -> DependencyInventory:
    """Walk the repo, parse every recognized manifest/lockfile/Dockerfile, and
    return the merged inventory."""
    if not repo_path.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path}")

    declared: list[Dependency] = []
    locked: list[Dependency] = []
    for file_path, relative in iter_workspace_files(repo_path):
        parser = next((p for p in _REGISTRY if p.matches(file_path.name.lower())), None)
        if parser is None:
            continue
        text = _read_text(file_path)
        if text is None:
            continue
        rows = parser.parse(text, relative)
        (declared if parser.side == "declared" else locked).extend(rows)

    merged = merge_locked(declared, locked)
    for dep in merged:
        if dep.name != normalize_package_name(dep.ecosystem, dep.name):
            raise AssertionError(f"dependency name not normalized: {dep.name!r}")
        if dep.ecosystem == "oci" and dep.locked_version is not None:
            raise AssertionError("oci deps lock via locked_hashes, never locked_version")
        if dep.declared_in is None and dep.locked_in is None:
            raise AssertionError("every dependency must cite a source file")

    return DependencyInventory(dependencies=merged)


def merge_locked(declared: list[Dependency], locked: list[Dependency]) -> list[Dependency]:
    """Fold lock rows into the declared rows they resolve; unmatched lock rows
    stay as ``direct=False`` closure entries.

    An identity is a join key, not a uniqueness constraint: universal locks
    (uv.lock, poetry.lock) list the same package several times when resolution
    forks on markers or platforms. A declared row matched by several forks
    keeps the first fork's version as the representative and the union of all
    forks' hashes — the hash set is what archival verification checks against,
    so no fork's artifacts may be dropped.
    """
    if any(lock.direct for lock in locked):
        raise AssertionError("lock rows are closure facts and must arrive with direct=False")

    by_identity: dict[tuple[str, str], list[Dependency]] = {}
    for lock in locked:
        by_identity.setdefault((lock.ecosystem, lock.name), []).append(lock)

    matched: set[tuple[str, str]] = set()
    merged: list[Dependency] = []
    for dep in declared:
        forks = by_identity.get((dep.ecosystem, dep.name))
        if forks:
            all_hashes = [h for fork in forks for h in fork.locked_hashes]
            dep = dep.model_copy(
                update={
                    "locked_version": forks[0].locked_version,
                    "locked_hashes": list(dict.fromkeys(all_hashes)),
                    "locked_in": forks[0].locked_in,
                }
            )
            matched.add((dep.ecosystem, dep.name))
        merged.append(dep)
    merged.extend(lock for lock in locked if (lock.ecosystem, lock.name) not in matched)

    if [(d.ecosystem, d.name) for d in merged[: len(declared)]] != [(d.ecosystem, d.name) for d in declared]:
        raise AssertionError("merge must preserve every declared row, in order")
    if {(d.ecosystem, d.name) for d in merged} != {(d.ecosystem, d.name) for d in [*declared, *locked]}:
        raise AssertionError("merge must neither invent nor drop identities")

    return merged


# ================================================
# Workspace walk
# ================================================


def iter_workspace_files(repo_path: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(absolute path, repo-relative posix path)`` for every workspace
    file, in deterministic (per-directory sorted) order.

    Skipped directories are pruned — never descended into — which is both the
    performance win over ``rglob`` and a correctness rule: a manifest inside
    ``node_modules`` or a committed ``.venv`` is not the repo's own.
    """
    root = str(repo_path)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIPPED_DIRS)
        rel_dir = os.path.relpath(dirpath, root)
        prefix = "" if rel_dir == "." else rel_dir.replace(os.sep, "/") + "/"
        for name in sorted(filenames):
            yield Path(dirpath) / name, prefix + name


# ================================================
# Internals
# ================================================


def _read_text(file_path: Path) -> str | None:
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
