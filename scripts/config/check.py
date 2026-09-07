#!/usr/bin/env python3
"""Reject environment references that are absent from the formal contract."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from scripts.config.export import CONTRACT, ROOT, build_contract, rendered_contract

PYTHON_ROOTS = (
    "api/src",
    "core/src",
    "executor/src",
    "protocol/src",
    "provider/src",
    "supervisor/src",
    "workbench/src",
    "scripts",
)
TYPESCRIPT_ROOTS = ("gui/src", "gui/tests", "gui/scripts")
TYPESCRIPT_INPUTS = tuple(
    sorted(
        {
            path
            for root in TYPESCRIPT_ROOTS
            for suffix in ("*.js", "*.mjs", "*.ts", "*.tsx")
            for path in (ROOT / root).rglob(suffix)
        }
        | {path for suffix in ("*.js", "*.mjs", "*.ts") for path in (ROOT / "gui").glob(suffix) if path.is_file()}
    )
)
NIX_INPUTS = (ROOT / "flake.nix", *sorted((ROOT / "nix").rglob("*.nix")))
SHELL_INPUTS = tuple(
    path
    for path in sorted((ROOT / "scripts").rglob("*"))
    if path.is_file() and (path.suffix == ".sh" or not path.suffix)
)
TEXT_INPUTS = (
    ROOT / ".envrc",
    ROOT / "justfile",
    *sorted((ROOT / "just").glob("*.just")),
    *sorted(ROOT.glob("docker-compose*.yml")),
    *SHELL_INPUTS,
)
DOCKER_INPUTS = tuple(sorted((ROOT / "docker").rglob("Dockerfile"))) + tuple(
    sorted((ROOT / "docker").rglob("*.Dockerfile"))
)

VITE_BUILTINS = frozenset({"BASE_URL", "DEV", "MODE", "PROD", "SSR"})
Access = Literal["read", "write", "pass-through", "generated"]


@dataclass(frozen=True)
class EnvironmentReference:
    name: str
    path: Path
    line: int
    access: Access


def _reference(name: str, path: Path, line: int, access: Access = "read") -> EnvironmentReference:
    return EnvironmentReference(name=name, path=path, line=line, access=access)


def python_environment_references(path: Path) -> set[EnvironmentReference]:
    references: set[EnvironmentReference] = set()
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if (
                node.func.attr in {"get", "setdefault", "pop"}
                and isinstance(owner, ast.Attribute)
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "os"
                and owner.attr == "environ"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                access: Access = "write" if node.func.attr == "setdefault" else "read"
                references.add(_reference(node.args[0].value, path, node.lineno, access))
            if (
                node.func.attr == "getenv"
                and isinstance(owner, ast.Name)
                and owner.id == "os"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                references.add(_reference(node.args[0].value, path, node.lineno))
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            owner = node.value
            if (
                isinstance(owner.value, ast.Name)
                and owner.value.id == "os"
                and owner.attr == "environ"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                access = "write" if isinstance(node.ctx, ast.Store) else "read"
                references.add(_reference(node.slice.value, path, node.lineno, access))
    return references


def typescript_environment_references(path: Path) -> set[EnvironmentReference]:
    references: set[EnvironmentReference] = set()
    patterns: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
        (re.compile(r"\bprocess\.env\.([A-Z][A-Z0-9_]*)"), frozenset()),
        (re.compile(r"\bimport\.meta\.env\.([A-Z][A-Z0-9_]*)"), VITE_BUILTINS),
    )
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        for pattern, ignored in patterns:
            references.update(
                _reference(name, path, line_number) for name in pattern.findall(line) if name not in ignored
            )
    return references


def text_environment_references(path: Path) -> set[EnvironmentReference]:
    references: set[EnvironmentReference] = set()
    patterns: tuple[tuple[re.Pattern[str], Access], ...] = (
        (re.compile(r'env\("([A-Z][A-Z0-9_]*)"'), "read"),
        (re.compile(r"\$\{([A-Z][A-Z0-9_]*)"), "read"),
        (re.compile(r"^\s*([A-Z][A-Z0-9_]*)="), "pass-through"),
    )
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        for pattern, access in patterns:
            references.update(_reference(name, path, line_number, access) for name in pattern.findall(line))
    return references


def embedded_shell_environment_references(path: Path) -> set[EnvironmentReference]:
    """Find environment-style parameter expansion inside generated shell text.

    Uppercase assignments in those templates are ordinary shell locals, so the
    broader shell scanner would incorrectly turn each of them into a contract
    entry. Default-value parameter expansion is the deliberate external-input
    shape used by generated scripts.
    """
    references: set[EnvironmentReference] = set()
    pattern = re.compile(r"\$\{([A-Z][A-Z0-9_]*):-")
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        references.update(_reference(name, path, line_number, "generated") for name in pattern.findall(line))
    return references


def nix_environment_references(path: Path) -> set[EnvironmentReference]:
    references = text_environment_references(path)
    pattern = re.compile(r'\bbuiltins\.getEnv\s+"([A-Z][A-Z0-9_]*)"')
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        references.update(_reference(name, path, line_number) for name in pattern.findall(line))
    return references


def docker_environment_references(path: Path) -> set[EnvironmentReference]:
    references = text_environment_references(path)
    arg_pattern = re.compile(r"^\s*ARG\s+([A-Z][A-Z0-9_]*)(?:=|\s|$)")
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if match := arg_pattern.match(line):
            references.add(_reference(match.group(1), path, line_number, "read"))
    return references


def referenced_environment() -> dict[str, set[EnvironmentReference]]:
    references: dict[str, set[EnvironmentReference]] = {}

    def collect(found: set[EnvironmentReference]) -> None:
        for reference in found:
            references.setdefault(reference.name, set()).add(reference)

    for root_name in PYTHON_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            if "tests" in path.relative_to(ROOT / root_name).parts:
                continue
            collect(python_environment_references(path))
            # Generated shell programs live in Python string literals. Reading
            # the raw source catches their defaulted environment inputs as well.
            collect(embedded_shell_environment_references(path))
    for path in TYPESCRIPT_INPUTS:
        collect(typescript_environment_references(path))
    for path in NIX_INPUTS:
        collect(nix_environment_references(path))
    for path in DOCKER_INPUTS:
        collect(docker_environment_references(path))
    for path in TEXT_INPUTS:
        collect(text_environment_references(path))
    return references


def _declared(name: str, exact: set[str], patterns: tuple[re.Pattern[str], ...]) -> bool:
    return name in exact or any(pattern.fullmatch(name) for pattern in patterns)


def main() -> int:
    contract = build_contract()
    declared = set(contract["variables"])
    declared_patterns = tuple(re.compile(pattern) for pattern in contract["patterns"])
    references = referenced_environment()
    unknown = sorted(name for name in references if not _declared(name, declared, declared_patterns))
    if unknown:
        for name in unknown:
            print(f"undeclared environment variable {name}")
            for reference in sorted(references[name], key=lambda item: (item.path, item.line, item.access)):
                print(f"  {reference.access:12} {reference.path.relative_to(ROOT)}:{reference.line}")
        return 1
    if not CONTRACT.exists() or CONTRACT.read_text() != rendered_contract():
        print("configuration contract is stale; run: just config-export")
        return 1
    print(f"configuration contract valid: {len(declared)} variables, {len(declared_patterns)} patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
