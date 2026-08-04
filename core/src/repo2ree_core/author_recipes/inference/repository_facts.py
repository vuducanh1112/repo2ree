"""Normalized repository facts, scanned once per inference request.

Two responsibilities live here:

1. ``resolve_logical_root`` — a single pure function that peels wrapper
   directories off an extracted source tree to find the logical project root. It
   takes *only* a directory path: no acquisition kind, no persisted layout fact.
   A git clone lands contents at the extraction root; a source archive commonly
   wraps everything under one ``project-name-main/`` directory. Both resolve
   through the same structural rule.

2. ``scan_repository`` — builds ``RepositoryFacts`` from the immutable acquired
   ``upstream`` tree. Scanning *upstream* (never the materialized workspace) is
   the load-bearing scoping rule that keeps inference from discovering its own
   output — reserved scripts, generated recipes, runtime artifacts — as
   evidence, and it needs no digest to hold.

Facts are deliberately richer than the aggregate reproducibility report:
generation decisions need physical paths, normalized project-root-relative
paths, and structural ambiguity, all of which the report's levels flatten away.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.digests import digest_bytes

SCANNER_VERSION = 1

# Bump when any rule in ``resolve_logical_root`` changes, so a resolved root can
# be invalidated.
LAYOUT_VERSION = 1

# Entries that never count toward the wrapper decision (kept as source; just not
# "meaningful" for structure).
_IGNORED: frozenset[str] = frozenset({"__MACOSX", ".DS_Store", "pax_global_header"})

# Presence of any of these at a level means "this level is a project root" —
# stop descending, even if it also holds a single subdirectory.
_ROOT_MARKERS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".repo2ree",
        "Dockerfile",
        "Containerfile",
        "docker-compose.yml",
        "compose.yaml",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "environment.yml",
        "environment.yaml",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
    }
)

_MAX_DEPTH = 8  # guard against pathological wrapper chains


def resolve_logical_root(root: Path) -> str:
    """Resolve a repo's logical project root from a directory path alone.

    Returns a POSIX path relative to ``root``: ``"."`` when ``root`` is already
    the logical root, else the wrapper chain that leads to it (e.g.
    ``"project-name-main"`` or, rarely, ``"a/b"``).

    Purely structural: it peels directories that contain exactly one meaningful
    child directory and nothing else, and stops the moment a level carries a
    project-root marker, has zero or several meaningful entries, or its lone
    entry is a file/symlink rather than a real directory.
    """
    current = root
    rel = PurePosixPath()

    for _ in range(_MAX_DEPTH):
        meaningful: list[os.DirEntry[str]] = []
        has_marker = False
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.name in _IGNORED:
                        continue
                    if entry.name in _ROOT_MARKERS:
                        has_marker = True
                    meaningful.append(entry)
                    if len(meaningful) > 1 and has_marker:
                        break  # already enough to decide "stop here"
        except OSError:
            break

        # This level looks like a real root: stop, don't unwrap past it.
        if has_marker:
            break

        # A single meaningful entry that is a *real* directory is a wrapper —
        # descend. Anything else (empty, a lone file/symlink, or several
        # entries) means this level is the logical root.
        if len(meaningful) == 1 and meaningful[0].is_dir(follow_symlinks=False):
            current = Path(meaningful[0].path)
            rel = rel / meaningful[0].name
            continue
        break

    # Postcondition: we only ever peel *into* real directories, so a non-"."
    # result must name an existing directory beneath ``root``. Guards a peeling
    # bug from silently producing a bogus project root.
    if rel.parts and not (root / str(rel)).is_dir():
        raise AssertionError(f"resolve_logical_root peeled to a non-directory: {rel}")
    return str(rel) if rel.parts else "."


# ================================================
# Fact models
# ================================================


class DockerfileFact(BaseModel):
    """A Dockerfile/Containerfile found in the scanned tree.

    Phase 1 build inference is purely locational: it reads *where* Dockerfiles
    are, never *what they contain*. ``at_project_root`` marks a Dockerfile that
    sits directly inside the logical project root (its build context is that
    root); anything deeper is ``nested`` and structurally ambiguous.
    """

    model_config = ConfigDict(extra="forbid")

    # POSIX path relative to the scanned tree root (includes any wrapper chain).
    path: str
    # POSIX path relative to the logical project root.
    project_relative_path: str
    digest: str
    at_project_root: bool


class RequirementsFact(BaseModel):
    """A pip ``requirements.txt`` found in the scanned tree.

    ``at_project_root`` marks a requirements file sitting directly inside the
    logical project root — the only location the ``root-pip-requirements-v1``
    strategy fires for. requirements.txt is not a lockfile, which downstream
    rendering reflects as a non-blocking ``dependencies_not_locked`` warning.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    project_relative_path: str
    digest: str
    at_project_root: bool


class RepositoryFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanner_version: int = SCANNER_VERSION
    layout_version: int = LAYOUT_VERSION
    # Output of ``resolve_logical_root`` over the scanned tree: "." or a wrapper
    # chain such as "project-name-main". No acquisition-kind input is recorded.
    logical_project_root: str
    dockerfiles: list[DockerfileFact] = Field(default_factory=list)
    requirements_files: list[RequirementsFact] = Field(default_factory=list)


# ================================================
# Scan
# ================================================

# Directories never descended into: build inference must not discover a
# Dockerfile vendored inside a dependency tree as the repo's own.
_SKIPPED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".repo2ree",
    }
)


def _is_dockerfile_name(name: str) -> bool:
    lower = name.lower()
    return lower in {"dockerfile", "containerfile"} or lower.startswith(("dockerfile.", "containerfile."))


def scan_repository(repo_path: Path) -> RepositoryFacts:
    """Scan an extracted source tree into normalized facts.

    ``repo_path`` is the extraction root (``upstream`` in the workbench layout).
    The logical project root is resolved first; runtime-relevant files
    (Dockerfiles, requirements.txt) are then recorded relative to both the
    scanned tree and that logical root, in one pruned walk.
    """
    if not repo_path.is_dir():
        raise ValueError(f"repo_path must be an existing directory: {repo_path}")

    logical_root = resolve_logical_root(repo_path)
    logical_root_posix = PurePosixPath() if logical_root == "." else PurePosixPath(logical_root)

    dockerfiles: list[DockerfileFact] = []
    requirements_files: list[RequirementsFact] = []
    root_str = str(repo_path)
    for dirpath, dirnames, filenames in os.walk(root_str):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIPPED_DIRS and d not in _IGNORED)
        rel_dir = os.path.relpath(dirpath, root_str)
        prefix = PurePosixPath() if rel_dir == "." else PurePosixPath(rel_dir.replace(os.sep, "/"))
        for name in sorted(filenames):
            is_dockerfile = _is_dockerfile_name(name)
            is_requirements = name.lower() == "requirements.txt"
            if not (is_dockerfile or is_requirements):
                continue
            rel_path = prefix / name
            try:
                digest = digest_bytes((Path(dirpath) / name).read_bytes())
            except OSError:
                continue
            project_relative = _relative_to_project_root(rel_path, logical_root_posix)
            project_relative_str = str(project_relative) if project_relative is not None else str(rel_path)
            at_project_root = project_relative is not None and len(project_relative.parts) == 1
            if is_dockerfile:
                dockerfiles.append(
                    DockerfileFact(
                        path=str(rel_path),
                        project_relative_path=project_relative_str,
                        digest=digest,
                        at_project_root=at_project_root,
                    )
                )
            else:
                requirements_files.append(
                    RequirementsFact(
                        path=str(rel_path),
                        project_relative_path=project_relative_str,
                        digest=digest,
                        at_project_root=at_project_root,
                    )
                )

    return RepositoryFacts(
        logical_project_root=logical_root,
        dockerfiles=dockerfiles,
        requirements_files=requirements_files,
    )


def _relative_to_project_root(rel_path: PurePosixPath, logical_root: PurePosixPath) -> PurePosixPath | None:
    """Path of ``rel_path`` relative to the logical project root, or ``None`` if
    it lies outside that root (above or in a sibling of the wrapper chain)."""
    if not logical_root.parts:
        return rel_path
    try:
        return rel_path.relative_to(logical_root)
    except ValueError:
        return None
