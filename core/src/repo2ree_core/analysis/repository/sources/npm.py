from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from repo2ree_ree.dependency import Dependency, normalize_package_name

from ._common import make_dependency, make_locked_dependency
from .base import SourceParser

_DECLARATION_SECTIONS: tuple[tuple[str, str | None], ...] = (
    ("dependencies", None),
    ("devDependencies", "dev"),
    ("optionalDependencies", "optional"),
    ("peerDependencies", "peer"),
)


def parse_package_json(text: str, path: str) -> list[Dependency]:
    data = _load_json_object(text)
    if data is None:
        return []
    deps: list[Dependency] = []
    seen: set[str] = set()
    for section, scope in _DECLARATION_SECTIONS:
        entries = data.get(section)
        if not isinstance(entries, dict):
            continue
        for raw_name, constraint in entries.items():
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            name = normalize_package_name("npm", raw_name)
            if name in seen:
                continue
            seen.add(name)
            deps.append(
                make_dependency(
                    "npm",
                    raw_name,
                    declared_constraint=constraint if isinstance(constraint, str) and constraint else None,
                    declared_in=path,
                    scope=scope,
                )
            )
    return deps


def parse_package_lock(text: str, path: str) -> list[Dependency]:
    data = _load_json_object(text)
    if data is None:
        return []
    packages = data.get("packages")
    if isinstance(packages, dict):
        return _dedupe_locked(_parse_packages_map(packages, path))
    dependencies = data.get("dependencies")
    if not isinstance(dependencies, dict):
        return []
    return _dedupe_locked(_parse_v1_dependencies(dependencies, path))


def _parse_packages_map(packages: dict[str, Any], path: str) -> Iterator[Dependency]:
    for install_path, package in packages.items():
        if not isinstance(install_path, str) or not isinstance(package, dict):
            continue
        raw_name = _name_from_install_path(install_path)
        if raw_name is None:
            continue
        yield make_locked_dependency(
            "npm",
            raw_name,
            locked_version=package.get("version"),
            locked_hashes=[str(package["integrity"])] if package.get("integrity") else [],
            locked_in=path,
        )


def _parse_v1_dependencies(entries: dict[str, Any], path: str) -> Iterator[Dependency]:
    stack: list[dict[str, Any]] = [entries]
    while stack:
        for raw_name, package in stack.pop().items():
            if not isinstance(raw_name, str) or not raw_name.strip() or not isinstance(package, dict):
                continue
            yield make_locked_dependency(
                "npm",
                raw_name,
                locked_version=package.get("version"),
                locked_hashes=[str(package["integrity"])] if package.get("integrity") else [],
                locked_in=path,
            )
            nested = package.get("dependencies")
            if isinstance(nested, dict):
                stack.append(nested)


def _dedupe_locked(rows: Iterator[Dependency]) -> list[Dependency]:
    by_resolution: dict[tuple[str, str | None], Dependency] = {}
    for row in rows:
        key = (row.name, row.locked_version)
        kept = by_resolution.get(key)
        if kept is None:
            by_resolution[key] = row
        elif row.locked_hashes:
            kept.locked_hashes = list(dict.fromkeys([*kept.locked_hashes, *row.locked_hashes]))
    return list(by_resolution.values())


def _name_from_install_path(install_path: str) -> str | None:
    marker = "node_modules/"
    if marker not in install_path:
        return None
    candidate = install_path.rsplit(marker, 1)[1]
    if not candidate.strip():
        return None
    return candidate


def _load_json_object(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


PARSERS: tuple[SourceParser, ...] = (
    SourceParser(
        format_id="package-json",
        side="declared",
        matches=lambda name: name == "package.json",
        parse=parse_package_json,
    ),
    SourceParser(
        format_id="npm-lock",
        side="locked",
        matches=lambda name: name in {"package-lock.json", "npm-shrinkwrap.json"},
        parse=parse_package_lock,
    ),
)
