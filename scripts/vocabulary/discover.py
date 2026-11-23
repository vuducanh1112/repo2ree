from __future__ import annotations

import ast
import json
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.vocabulary.model import CONTRACTS, Contract, Located

ROOT = Path(__file__).resolve().parents[2]


def escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def contract_sets(contract: Contract, document: Any) -> Iterator[Located]:
    def walk(value: Any, pointer: str) -> Iterator[Located]:
        if isinstance(value, dict):
            enum = value.get("enum")
            if isinstance(enum, list) and enum and all(isinstance(item, str) for item in enum):
                yield Located(f"{contract}:{pointer}/enum", frozenset(enum))
            properties = value.get("properties")
            if isinstance(properties, dict) and properties:
                yield Located(f"{contract}:{pointer}/properties", frozenset(properties))
            for key, child in value.items():
                yield from walk(child, f"{pointer}/{escape(str(key))}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, f"{pointer}/{index}")

    yield from walk(document, "")


def load_contract(contract: Contract) -> Any:
    return json.loads((ROOT / CONTRACTS[contract]).read_text(encoding="utf-8"))


def tracked(*patterns: str) -> list[str]:
    listed = subprocess.run(["git", "ls-files", *patterns], cwd=ROOT, capture_output=True, text=True, check=True)
    return listed.stdout.split()


def _strings(nodes: list[ast.expr]) -> list[str] | None:
    values = [node.value for node in nodes if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    return values if len(values) == len(nodes) else None


def _python_sets(tree: ast.Module) -> Iterator[tuple[ast.AST, list[str]]]:
    literal_slices: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and getattr(node.value, "id", getattr(node.value, "attr", None)) == "Literal"
        ):
            elements = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            literal_slices.add(id(node.slice))
            if (values := _strings(elements)) is not None:
                yield node, values
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple | ast.List | ast.Set) and id(node) not in literal_slices:
            if (values := _strings(list(node.elts))) is not None:
                yield node, values
        elif (
            isinstance(node, ast.Dict)
            and node.keys
            and all(key is not None for key in node.keys)
            and (values := _strings([key for key in node.keys if key is not None])) is not None
        ):
            yield node, values


def _symbol(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    parts: list[str] = []
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(id(current))
        if isinstance(parent, ast.Assign) and parent.targets and current is parent.value:
            parts.append(ast.unparse(parent.targets[0]))
        elif isinstance(parent, ast.AnnAssign) and current is parent.value:
            parts.append(ast.unparse(parent.target))
        elif isinstance(parent, ast.keyword) and parent.arg:
            parts.append(parent.arg)
        elif isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            parts.append(parent.name)
        current = parent
    return ".".join(reversed(parts)) or "<module>"


def python_sites(path: str, source: str, roots: frozenset[str]) -> dict[str, Located]:
    tree = ast.parse(source)
    parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    sites: dict[str, Located] = {}
    for node, values in _python_sets(tree):
        if len(values) < 2 or not set(values) & roots:
            continue
        site = f"{path}::{_symbol(node, parents)}"
        while site in sites:
            site += "+"
        sites[site] = Located(site, frozenset(values))
    return sites


_NAME = r"[a-z][a-z0-9_]*"
SITES_SCRIPT = "gui/scripts/vocabularySites.mjs"


@dataclass(frozen=True)
class TypescriptSet:
    path: str
    declaration: str
    start: int
    names: tuple[str, ...]


def typescript_sets(paths: list[str], root: Path = ROOT) -> list[TypescriptSet]:
    if not paths:
        return []
    listed = subprocess.run(
        ["node", str(ROOT / SITES_SCRIPT), *paths], cwd=root, capture_output=True, text=True, check=True
    )
    return [
        TypescriptSet(found["path"], found["declaration"], found["start"], tuple(found["names"]))
        for found in json.loads(listed.stdout)
    ]


def typescript_sites(sets: list[TypescriptSet], roots: frozenset[str]) -> dict[str, Located]:
    sites: dict[str, Located] = {}
    for found in sorted(sets, key=lambda found: (found.path, found.start, found.names)):
        if len(found.names) < 2 or not set(found.names) & roots:
            continue
        site = f"{found.path}::{found.declaration}"
        while site in sites:
            site += "+"
        sites[site] = Located(site, frozenset(found.names))
    return sites


def biome_sites(path: str, source: str, roots: frozenset[str]) -> dict[str, Located]:
    sites: dict[str, Located] = {}
    for index, match in enumerate(re.finditer(r'"match":\s*"([^"]+)"', source)):
        values = [part for part in match.group(1).split("|") if re.fullmatch(_NAME, part)]
        if len(values) >= 2 and set(values) & roots:
            site = f"{path}::match.{index}"
            sites[site] = Located(site, frozenset(values))
    return sites


def source_sites(roots: frozenset[str]) -> dict[str, Located]:
    sites: dict[str, Located] = {}
    for path in tracked("*.py"):
        if "/src/" in path and "/tests/" not in path:
            sites |= python_sites(path, (ROOT / path).read_text(encoding="utf-8"), roots)
    gui = [
        path for path in tracked("gui/src/*.ts", "gui/src/*.tsx") if ".test." not in path and "/generated/" not in path
    ]
    sites |= typescript_sites(typescript_sets(gui), roots)
    sites |= biome_sites("gui/biome.json", (ROOT / "gui/biome.json").read_text(encoding="utf-8"), roots)
    return sites
