"""pypi ecosystem parsers.

Declared side: ``requirements*.txt`` and ``pyproject.toml`` (PEP 621 and the
poetry table). Locked side: ``uv.lock`` and ``poetry.lock`` — both universal
locks, so the same package may appear once per marker/platform fork.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from repo2ree_core.domain.dependency import Dependency

from ._common import dependency_from_pep508, load_toml, make_dependency, make_locked_dependency
from .base import SourceParser

_REQUIREMENTS_RE = re.compile(r"^requirements([-_].+)?\.txt$")

_HASH_OPTION_RE = re.compile(r"--hash[= ](\S+)")


# ================================================
# Declared side
# ================================================


def parse_requirements_txt(text: str, path: str) -> list[Dependency]:
    deps: list[Dependency] = []
    for line in _logical_lines(text):
        if line.startswith(("-", ".", "/")) or "://" in line:
            continue  # pip options, URL requirements, local paths
        hashes = _HASH_OPTION_RE.findall(line)
        spec = _HASH_OPTION_RE.sub("", line).split(";", 1)[0].strip()
        dep = dependency_from_pep508(spec, path)
        if dep is None:
            continue
        if hashes:
            # Hash-mode requirements are a lock: pip refuses anything but
            # these artifacts.
            exact = (dep.declared_constraint or "").removeprefix("==").strip()
            dep = dep.model_copy(
                update={
                    "locked_version": exact or None,
                    "locked_hashes": hashes,
                    "locked_in": path,
                }
            )
        deps.append(dep)
    return deps


def parse_pyproject(text: str, path: str) -> list[Dependency]:
    data = load_toml(text)
    if data is None:
        return []
    deps: list[Dependency] = []

    project = data.get("project")
    if isinstance(project, dict):
        entries = project.get("dependencies")
        for entry in entries if isinstance(entries, list) else []:
            if isinstance(entry, str):
                dep = dependency_from_pep508(entry.split(";", 1)[0].strip(), path)
                if dep is not None:
                    deps.append(dep)

    tool = data.get("tool")
    poetry = tool.get("poetry") if isinstance(tool, dict) else None
    poetry_deps = poetry.get("dependencies") if isinstance(poetry, dict) else None
    if isinstance(poetry_deps, dict):
        for raw_name, constraint in poetry_deps.items():
            if raw_name.lower() == "python":
                continue  # the interpreter constraint, not a package
            if isinstance(constraint, dict):
                constraint = constraint.get("version")
            deps.append(
                make_dependency(
                    "pypi",
                    raw_name,
                    declared_constraint=str(constraint) if constraint else None,
                    declared_in=path,
                )
            )
    return deps


# ================================================
# Locked side
# ================================================


def parse_uv_lock(text: str, path: str) -> list[Dependency]:
    data = load_toml(text)
    if data is None:
        return []
    deps: list[Dependency] = []
    for package in data.get("package") or []:
        if not isinstance(package, dict) or not package.get("name"):
            continue
        source = package.get("source")
        if isinstance(source, dict) and ("virtual" in source or "editable" in source):
            continue  # the project itself, not a dependency
        hashes: list[str] = []
        sdist = package.get("sdist")
        if isinstance(sdist, dict) and sdist.get("hash"):
            hashes.append(str(sdist["hash"]))
        hashes.extend(
            str(wheel["hash"]) for wheel in package.get("wheels") or [] if isinstance(wheel, dict) and wheel.get("hash")
        )
        deps.append(
            make_locked_dependency(
                "pypi",
                str(package["name"]),
                locked_version=package.get("version"),
                locked_hashes=hashes,
                locked_in=path,
            )
        )
    return deps


def parse_poetry_lock(text: str, path: str) -> list[Dependency]:
    data = load_toml(text)
    if data is None:
        return []
    deps: list[Dependency] = []
    for package in data.get("package") or []:
        if not isinstance(package, dict) or not package.get("name"):
            continue
        hashes = [
            str(entry["hash"]) for entry in package.get("files") or [] if isinstance(entry, dict) and entry.get("hash")
        ]
        deps.append(
            make_locked_dependency(
                "pypi",
                str(package["name"]),
                locked_version=package.get("version"),
                locked_hashes=hashes,
                locked_in=path,
            )
        )
    return deps


# ================================================
# Internals
# ================================================


def _logical_lines(text: str) -> Iterator[str]:
    """requirements.txt lines with backslash continuations joined and comments
    stripped."""
    joined = re.sub(r"\\\s*\n", " ", text)
    for raw in joined.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            yield line


# ================================================
# Registry entries
# ================================================

PARSERS: tuple[SourceParser, ...] = (
    SourceParser(
        format_id="requirements-txt",
        side="declared",
        matches=lambda name: bool(_REQUIREMENTS_RE.match(name)),
        parse=parse_requirements_txt,
    ),
    SourceParser(
        format_id="pyproject-toml",
        side="declared",
        matches=lambda name: name == "pyproject.toml",
        parse=parse_pyproject,
    ),
    SourceParser(
        format_id="uv-lock",
        side="locked",
        matches=lambda name: name == "uv.lock",
        parse=parse_uv_lock,
    ),
    SourceParser(
        format_id="poetry-lock",
        side="locked",
        matches=lambda name: name == "poetry.lock",
        parse=parse_poetry_lock,
    ),
)
