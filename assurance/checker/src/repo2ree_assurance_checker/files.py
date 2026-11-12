"""Locate and read the specification files."""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from repo2ree_assurance_checker.spec import TREE_FORMAT, Spec, parse_spec

ROOT = Path(__file__).resolve().parents[4]
SPEC_DIR = ROOT / "assurance" / "spec"
# Where revisions before the assurance/ layout (2026-10-23) kept the specification.
LEGACY_SPEC_DIR = ROOT / "specifications" / "behaviour"
CONTRACT_DIR = ROOT / "contracts" / "behaviour"
GENERATED_SCHEMA = CONTRACT_DIR / "events.schema.json"


def with_tree(aggregate: dict[str, Any], read: Callable[[str], str]) -> dict[str, Any]:
    """An aggregate with the tree its ``tree`` names read in, from the repository root."""
    if "tree" not in aggregate:
        return aggregate
    contract = json.loads(read(aggregate["tree"]))
    if contract.get("format") != TREE_FORMAT:
        raise ValueError(f"{aggregate['tree']}: not a {TREE_FORMAT} document")
    return aggregate | {"layout": contract["root"]}


def read_from_root(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_spec(directory: Path = SPEC_DIR) -> Spec:
    def documents(subdirectory: str) -> list[dict[str, object]]:
        return [tomllib.loads(path.read_text()) for path in sorted((directory / subdirectory).glob("*.toml"))]

    def single(name: str) -> dict[str, object]:
        path = directory / name
        return tomllib.loads(path.read_text()) if path.exists() else {}

    return parse_spec(
        documents("vocabulary"),
        documents("entities"),
        documents("boundaries"),
        single("invariants.toml"),
        single("components.toml"),
        [with_tree(document, read_from_root) for document in documents("aggregates")],
    )


def load_spec_at(revision: str, executable: str = "git") -> Spec:
    """The specification as committed at a Git revision, for reviewing behavioural changes."""

    def run(*args: str) -> str:
        return subprocess.run([executable, "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout

    for directory in (SPEC_DIR, LEGACY_SPEC_DIR):
        relative = directory.relative_to(ROOT).as_posix()
        if paths := run("ls-tree", "-r", "--name-only", revision, "--", relative).split():
            break
    documents = {path: tomllib.loads(run("show", f"{revision}:{path}")) for path in paths if path.endswith(".toml")}

    def under(subdirectory: str) -> list[dict[str, Any]]:
        prefix = f"{relative}/{subdirectory}/"
        return [document for path, document in sorted(documents.items()) if path.startswith(prefix)]

    vocabulary, entities, boundaries = under("vocabulary"), under("entities"), under("boundaries")
    if not vocabulary:
        vocabulary, entities, boundaries = split_combined(entities, boundaries)
    return parse_spec(
        vocabulary,
        entities,
        boundaries,
        documents.get(f"{relative}/invariants.toml", {}),
        documents.get(f"{relative}/components.toml", {}),
        [with_tree(document, lambda path: run("show", f"{revision}:{path}")) for document in under("aggregates")],
    )


MACHINE_KEYS = frozenset(
    {"name", "initial", "terminal", "settles_before_close", "ends_with_owner", "reconciled_by", "transitions"}
)


def split_combined(
    entities: list[dict[str, Any]], boundaries: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Vocabulary and rules from a revision that kept both in one file per subject (before 2026-10-21)."""
    vocabulary = [
        {"kind": "entity"} | {key: value for key, value in document.items() if key not in MACHINE_KEYS - {"name"}}
        for document in entities
    ]
    vocabulary += [
        {"kind": "boundary"} | {key: value for key, value in document.items() if key != "cites"}
        for document in boundaries
    ]
    machines = [{key: value for key, value in document.items() if key in MACHINE_KEYS} for document in entities]
    exchanges = [{"name": document["name"], "cites": document.get("cites", [])} for document in boundaries]
    return vocabulary, machines, exchanges
