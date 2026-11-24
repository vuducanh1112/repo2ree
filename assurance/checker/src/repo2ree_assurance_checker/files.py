from __future__ import annotations

import json
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from repo2ree_assurance_checker.spec import TREE_FORMAT, Spec, operation_problems, parse_spec

ROOT = Path(__file__).resolve().parents[4]
SPEC_DIR = ROOT / "assurance" / "spec"
LEGACY_SPEC_DIR = ROOT / "specifications" / "behaviour"


def with_tree(aggregate: dict[str, Any], read: Callable[[str], str]) -> dict[str, Any]:
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

    spec = parse_spec(
        documents("vocabulary"),
        documents("entities"),
        documents("boundaries"),
        single("invariants.toml"),
        single("components.toml"),
        [with_tree(document, read_from_root) for document in documents("aggregates")],
        documents("documents"),
    )
    if problems := operation_problems(spec):
        raise ValueError("; ".join(problems))
    return spec


type SourceKind = Literal["vocabulary", "entities", "boundaries", "aggregates", "documents", "invariants", "components"]


SOURCE_KIND = TypeAdapter[SourceKind](SourceKind)


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    kind: SourceKind
    names: tuple[str, ...]


def _names(kind: SourceKind, document: dict[str, Any]) -> tuple[str, ...]:
    match kind:
        case "invariants":
            return tuple(str(invariant["id"]) for invariant in document.get("invariant", []))
        case "components":
            return tuple(str(component["name"]) for component in document.get("component", []))
        case "documents":
            return (str(document.get("document") or document["aggregate"]),)
        case _:
            return (str(document["name"]),)


def sources(documents: dict[str, dict[str, Any]], relative: str) -> tuple[Source, ...]:
    found = []
    for path, document in sorted(documents.items()):
        try:
            kind = SOURCE_KIND.validate_python(path.removeprefix(f"{relative}/").split("/")[0].removesuffix(".toml"))
        except ValidationError as error:
            raise ValueError(f"{path}: no part of the specification") from error
        found.append(Source(path=path, kind=kind, names=_names(kind, document)))
    return tuple(found)


def spec_sources(directory: Path = SPEC_DIR) -> tuple[Source, ...]:
    relative = directory.resolve().relative_to(ROOT).as_posix()
    documents = {
        path.resolve().relative_to(ROOT).as_posix(): tomllib.loads(path.read_text())
        for path in sorted(directory.rglob("*.toml"))
    }
    return sources(documents, relative)


def _documents_at(revision: str, executable: str) -> tuple[str, dict[str, dict[str, Any]]]:
    def run(*args: str) -> str:
        return subprocess.run([executable, "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout

    for directory in (SPEC_DIR, LEGACY_SPEC_DIR):
        relative = directory.relative_to(ROOT).as_posix()
        if paths := run("ls-tree", "-r", "--name-only", revision, "--", relative).split():
            break
    return relative, {
        path: tomllib.loads(run("show", f"{revision}:{path}")) for path in paths if path.endswith(".toml")
    }


def spec_sources_at(revision: str, executable: str = "git") -> tuple[Source, ...]:
    relative, documents = _documents_at(revision, executable)
    return sources(documents, relative)


def load_spec_at(revision: str, executable: str = "git") -> Spec:
    def run(*args: str) -> str:
        return subprocess.run([executable, "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout

    relative, documents = _documents_at(revision, executable)

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
        under("documents"),
    )


MACHINE_KEYS = frozenset(
    {"name", "initial", "terminal", "settles_before_close", "ends_with_owner", "reconciled_by", "transitions"}
)


def split_combined(
    entities: list[dict[str, Any]], boundaries: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
