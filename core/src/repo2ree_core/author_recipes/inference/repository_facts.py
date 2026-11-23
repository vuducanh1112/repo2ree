from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.digest import digest_bytes

SCANNER_VERSION = 1

LAYOUT_VERSION = 1

_IGNORED: frozenset[str] = frozenset({"__MACOSX", ".DS_Store", "pax_global_header"})

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

_MAX_DEPTH = 8


def resolve_logical_root(root: Path) -> str:
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
                        break
        except OSError:
            break

        if has_marker:
            break

        if len(meaningful) == 1 and meaningful[0].is_dir(follow_symlinks=False):
            current = Path(meaningful[0].path)
            rel = rel / meaningful[0].name
            continue
        break

    if rel.parts and not (root / str(rel)).is_dir():
        raise AssertionError(f"resolve_logical_root peeled to a non-directory: {rel}")
    return str(rel) if rel.parts else "."


class DockerfileFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    project_relative_path: str
    digest: str
    at_project_root: bool


class RequirementsFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    project_relative_path: str
    digest: str
    at_project_root: bool
    hash_locked: bool


class RepositoryFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanner_version: int = SCANNER_VERSION
    layout_version: int = LAYOUT_VERSION
    logical_project_root: str
    dockerfiles: list[DockerfileFact] = Field(default_factory=list)
    requirements_files: list[RequirementsFact] = Field(default_factory=list)


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
                content = (Path(dirpath) / name).read_bytes()
            except OSError:
                continue
            digest = digest_bytes(content)
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
                        hash_locked=_hash_locked(content),
                    )
                )

    return RepositoryFacts(
        logical_project_root=logical_root,
        dockerfiles=dockerfiles,
        requirements_files=requirements_files,
    )


def _hash_locked(content: bytes) -> bool:
    joined = re.sub(r"\\\s*\n", " ", content.decode("utf-8", errors="replace"))
    lines = (raw.split("#", 1)[0].strip() for raw in joined.splitlines())
    requirements = [line for line in lines if line and not line.startswith("-")]
    return all("--hash" in line for line in requirements)


def _relative_to_project_root(rel_path: PurePosixPath, logical_root: PurePosixPath) -> PurePosixPath | None:
    if not logical_root.parts:
        return rel_path
    try:
        return rel_path.relative_to(logical_root)
    except ValueError:
        return None
