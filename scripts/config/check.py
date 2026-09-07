#!/usr/bin/env python3
"""Reject environment references that are absent from the formal contract."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.config.export import CONTRACT, ROOT, build_contract, rendered_contract

PYTHON_ROOTS = ("api/src", "core/src", "executor/src", "protocol/src", "provider/src", "workbench/src")
SHELL_INPUTS = tuple(
    path
    for path in sorted((ROOT / "scripts").rglob("*"))
    if path.is_file() and (path.suffix == ".sh" or not path.suffix)
)
TEXT_INPUTS = (
    ROOT / "justfile",
    *sorted((ROOT / "just").glob("*.just")),
    *sorted(ROOT.glob("docker-compose*.yml")),
    *SHELL_INPUTS,
)


def python_environment_references(path: Path) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if (
                node.func.attr == "get"
                and isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "os"
                and owner.attr == "environ"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                names.add(node.args[0].value)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            owner = node.value
            if (
                isinstance(owner.value, ast.Name)
                and owner.value.id == "os"
                and owner.attr == "environ"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                names.add(node.slice.value)
    return names


def referenced_environment() -> dict[str, set[Path]]:
    references: dict[str, set[Path]] = {}
    for root_name in PYTHON_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            for name in python_environment_references(path):
                references.setdefault(name, set()).add(path)
    patterns = (
        re.compile(r'env\("([A-Z][A-Z0-9_]*)"'),
        re.compile(r"\$\{([A-Z][A-Z0-9_]*)"),
        re.compile(r"(?m)^\s*([A-Z][A-Z0-9_]*)="),
    )
    for path in TEXT_INPUTS:
        text = "\n".join(line for line in path.read_text().splitlines() if not line.lstrip().startswith("#"))
        for pattern in patterns:
            for name in pattern.findall(text):
                references.setdefault(name, set()).add(path)
    return references


def main() -> int:
    declared = set(build_contract()["variables"])
    references = referenced_environment()
    unknown = sorted(set(references) - declared)
    if unknown:
        for name in unknown:
            locations = ", ".join(str(path.relative_to(ROOT)) for path in sorted(references[name]))
            print(f"undeclared environment variable {name}: {locations}")
        return 1
    if not CONTRACT.exists() or CONTRACT.read_text() != rendered_contract():
        print("configuration contract is stale; run: just config-export")
        return 1
    print(f"configuration contract valid: {len(declared)} variables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
