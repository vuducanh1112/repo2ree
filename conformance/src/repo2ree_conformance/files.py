"""Locate and read the specification files."""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

from repo2ree_conformance.spec import Spec, parse_spec

ROOT = Path(__file__).resolve().parents[3]
SPEC_DIR = ROOT / "specifications" / "behaviour"
CONTRACT_DIR = ROOT / "contracts" / "behaviour"
GENERATED_SCHEMA = CONTRACT_DIR / "events.schema.json"


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
    )


def load_spec_at(revision: str, executable: str = "git") -> Spec:
    """The specification as committed at a Git revision, for reviewing behavioural changes."""
    relative = SPEC_DIR.relative_to(ROOT).as_posix()

    def run(*args: str) -> str:
        return subprocess.run([executable, "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout

    paths = run("ls-tree", "-r", "--name-only", revision, "--", relative).split()
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
    )


MACHINE_KEYS = frozenset({"name", "initial", "terminal", "settles_before_close", "transitions"})


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
