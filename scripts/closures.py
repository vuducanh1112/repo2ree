#!/usr/bin/env python3
"""Resolve each shipped Python closure from uv.lock into nix/closures.json, which nix builds from.

- ``generate`` writes the file; ``check`` exits 1 when it is stale.
- ``stage-paths`` prints the workspace package directories the closures build from.

A closure is a root package declared in ``[tool.repo2ree.closures]``: its workspace packages, and,
per system, one wheel of every third-party package it reaches, with the URL and hash uv locked.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from packaging.markers import Marker
from packaging.tags import Tag, compatible_tags, cpython_tags
from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "nix" / "closures.json"
SCHEMA = "repo2ree-closures/1"
PYTHON = (3, 13)
GLIBC = (2, 42)
SYSTEMS = {"x86_64-linux": "x86_64", "aarch64-linux": "aarch64"}


def environment(machine: str) -> dict[str, str]:
    return {
        "implementation_name": "cpython",
        "implementation_version": f"{PYTHON[0]}.{PYTHON[1]}",
        "os_name": "posix",
        "platform_machine": machine,
        "platform_python_implementation": "CPython",
        "platform_release": "",
        "platform_system": "Linux",
        "platform_version": "",
        "python_full_version": f"{PYTHON[0]}.{PYTHON[1]}.0",
        "python_version": f"{PYTHON[0]}.{PYTHON[1]}",
        "sys_platform": "linux",
        "extra": "",
    }


def supported_tags(machine: str) -> list[Tag]:
    platforms = [f"manylinux_{GLIBC[0]}_{minor}_{machine}" for minor in range(GLIBC[1], 16, -1)]
    platforms += [f"manylinux2014_{machine}"]
    if machine == "x86_64":
        platforms += ["manylinux2010_x86_64", "manylinux1_x86_64"]
    return [*cpython_tags(PYTHON, platforms=platforms), *compatible_tags(PYTHON, platforms=platforms)]


def reached(packages: dict[str, dict[str, Any]], root: str, machine: str) -> set[str]:
    env = environment(machine)
    found: dict[str, set[str]] = {}
    pending: list[tuple[str, frozenset[str]]] = [(root, frozenset())]
    while pending:
        name, extras = pending.pop()
        known = found.get(name)
        if known is not None and extras <= known:
            continue
        found[name] = (known or set()) | extras
        package = packages[name]
        dependencies = list(package.get("dependencies", []))
        for extra in extras:
            dependencies += package.get("optional-dependencies", {}).get(extra, [])
        for dependency in dependencies:
            marker = dependency.get("marker")
            if marker and not Marker(marker).evaluate(env):
                continue
            pending.append((dependency["name"], frozenset(dependency.get("extra", []))))
    return set(found)


def best_wheel(package: dict[str, Any], tags: list[Tag]) -> dict[str, Any] | None:
    rank = {tag: index for index, tag in enumerate(tags)}
    best: tuple[int, dict[str, Any]] | None = None
    for wheel in package.get("wheels", []):
        filename = wheel["url"].rsplit("/", 1)[-1]
        position = min((rank[tag] for tag in parse_wheel_filename(filename)[3] if tag in rank), default=None)
        if position is not None and (best is None or position < best[0]):
            best = (position, wheel)
    return best[1] if best else None


def member(root: Path, name: str, path: str) -> dict[str, Any]:
    pyproject = tomllib.loads((root / path / "pyproject.toml").read_text(encoding="utf-8"))
    modules = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    return {
        "name": name,
        "path": path,
        "version": pyproject["project"]["version"],
        "modules": sorted(Path(module).name for module in modules),
    }


def closure(packages: dict[str, dict[str, Any]], root: str, base: Path = ROOT) -> dict[str, Any]:
    workspace: set[str] = set()
    systems: dict[str, list[dict[str, Any]]] = {}
    for system, machine in SYSTEMS.items():
        tags = supported_tags(machine)
        wheels = []
        for name in sorted(reached(packages, root, machine)):
            package = packages[name]
            if "editable" in package["source"]:
                workspace.add(name)
                continue
            wheel = best_wheel(package, tags)
            if wheel is None:
                raise ValueError(f"{name} {package['version']} has no wheel for {system}")
            filename = wheel["url"].rsplit("/", 1)[-1]
            wheels.append(
                {
                    "name": name,
                    "version": package["version"],
                    "url": wheel["url"],
                    "sha256": wheel["hash"].removeprefix("sha256:"),
                    "binary": not filename.endswith("-none-any.whl"),
                }
            )
        systems[system] = wheels
    return {
        "root": root,
        "workspace": [member(base, name, packages[name]["source"]["editable"]) for name in sorted(workspace)],
        "systems": systems,
    }


def render(root: Path = ROOT) -> str:
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    roots = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["repo2ree"]["closures"]
    packages = {package["name"]: package for package in lock["package"]}
    document = {
        "schema": SCHEMA,
        "python": f"{PYTHON[0]}.{PYTHON[1]}",
        "closures": {name: closure(packages, package, root) for name, package in sorted(roots.items())},
    }
    return json.dumps(document, indent=2) + "\n"


def stage_paths(document: dict[str, Any]) -> list[str]:
    return sorted({entry["path"] for value in document["closures"].values() for entry in value["workspace"]})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("generate", "check", "stage-paths"))
    args = parser.parse_args(argv)
    if args.command == "stage-paths":
        print(*stage_paths(json.loads(OUTPUT.read_text(encoding="utf-8"))))
        return 0
    try:
        document = render()
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if args.command == "generate":
        OUTPUT.write_text(document, encoding="utf-8")
        return 0
    if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != document:
        print(f"{OUTPUT.relative_to(ROOT)} is stale — run: just generate-closures", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
