from __future__ import annotations

import copy
import json
import re
import types
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from repo2ree_core.digests import digest_bytes, digest_json
from repo2ree_core.domain.ree.model import Ree, canonical_subject_digest
from repo2ree_core.time_utils import format_utc_instant, parse_utc_instant

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "ree"
SEALED = sorted((CONTRACT / "sealed").glob("*.json"))
CANONICAL = json.loads((CONTRACT / "canonical.json").read_text(encoding="utf-8"))
INVALID = json.loads((CONTRACT / "invalid.json").read_text(encoding="utf-8"))
EXTENSIONS = frozenset(json.loads((CONTRACT / "v1-extensions.json").read_text(encoding="utf-8"))["extensions"])


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pointer(document: Any, path: str) -> tuple[Any, str]:
    *parents, last = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]
    for part in parents:
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document, last


def patched(document: Any, operations: list[dict[str, Any]]) -> Any:
    document = copy.deepcopy(document)
    for operation in operations:
        if operation["op"] in {"remove", "move"}:
            parent, key = pointer(document, operation.get("from", operation["path"]))
            value = parent.pop(int(key) if isinstance(parent, list) else key)
            if operation["op"] == "remove":
                continue
        else:
            value = operation["value"]
        parent, key = pointer(document, operation["path"])
        if not isinstance(parent, list):
            parent[key] = value
        elif key == "-":
            parent.append(value)
        elif operation["op"] == "replace":
            parent[int(key)] = value
        else:
            parent.insert(int(key), value)
    return document


def holds_models(annotation: Any) -> bool:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return True
    return any(holds_models(arg) for arg in get_args(annotation))


def missing(annotation: Any, value: Any, path: str) -> list[str]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found = []
        for name, field in annotation.model_fields.items():
            child = f"{path}.{name}" if path else name
            if name in value:
                found += missing(field.annotation, value[name], child)
            elif child not in EXTENSIONS:
                found.append(child)
        return found
    origin = get_origin(annotation)
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if origin in (Union, types.UnionType) and len(args) == 1:
        return missing(args[0], value, path)
    if origin is dict and holds_models(args[1]):
        entries, annotation = list(value.values()), args[1]
    elif origin is tuple and holds_models(args[0]):
        entries, annotation = value, args[0]
    else:
        return []
    if not entries:
        return [f"{path} (empty)"]
    return [item for entry in entries for item in missing(annotation, entry, path)]


@pytest.mark.parametrize("path", SEALED, ids=lambda path: path.stem)
def test_a_sealed_document_keeps_its_seal(path: Path) -> None:
    document = load(path)
    ree = Ree.model_validate(document)

    assert ree.seal is not None
    assert canonical_subject_digest(ree.subject) == document["seal"]["ree_digest"]
    assert ree.model_dump(mode="json", exclude_none=True) == document


def test_the_maximal_document_sets_every_field_but_the_extensions() -> None:
    assert missing(Ree, load(CONTRACT / "sealed" / "maximal.json"), "") == []


@pytest.mark.parametrize("vector", CANONICAL["digests"], ids=lambda vector: vector["name"])
def test_canonical_json_digest(vector: dict[str, Any]) -> None:
    assert digest_json(vector["value"]) == vector["digest"]
    assert digest_bytes(vector["canonical"].encode("utf-8")) == vector["digest"]


@pytest.mark.parametrize("vector", CANONICAL["instants"], ids=lambda vector: vector["name"])
def test_canonical_instant(vector: dict[str, str]) -> None:
    assert format_utc_instant(parse_utc_instant(vector["value"])) == vector["canonical"]


def test_the_invalid_base_is_valid_unsealed() -> None:
    Ree.model_validate(patched(load(CONTRACT / INVALID["base"]), [{"op": "remove", "path": "/seal"}]))


@pytest.mark.parametrize("case", INVALID["cases"], ids=lambda case: case["name"])
def test_an_invalid_document_is_refused(case: dict[str, Any]) -> None:
    document = patched(load(CONTRACT / INVALID["base"]), case["patch"])

    with pytest.raises(ValidationError, match=re.escape(case["error"])):
        Ree.model_validate(document)
