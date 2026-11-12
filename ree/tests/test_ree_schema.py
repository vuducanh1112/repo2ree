from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest
from jsonschema import Draft202012Validator

from repo2ree_ree.export_schema import LAYOUT_PATH, SCHEMA_PATH, schema_document
from repo2ree_ree.layout import REE_TREE, layout_document

SEALED = sorted((SCHEMA_PATH.parent / "sealed").glob("*.json"))


def test_the_committed_schema_is_current() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_document(), "run: just generate-ree-schema"


def test_the_committed_layout_is_current() -> None:
    assert LAYOUT_PATH.read_text(encoding="utf-8") == layout_document(), "run: just generate-ree-schema"


@pytest.mark.parametrize("path", SEALED, ids=lambda path: path.stem)
def test_a_sealed_document_conforms_to_the_schema(path: Path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(path.read_text(encoding="utf-8")))


def annotated(prop: dict[str, object], key: str) -> object:
    """An ``x-`` annotation on a property, on its non-null branch, or on its items."""
    for place in (prop, *prop.get("anyOf", []), prop.get("items", {})):  # type: ignore[misc]
        if isinstance(place, dict) and key in place:
            return place[key]
    return None


def fields() -> list[tuple[str, str, dict[str, object]]]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [
        (definition, name, prop)
        for definition, body in schema["$defs"].items()
        for name, prop in body.get("properties", {}).items()
    ]


def test_every_digest_says_what_in_the_tree_it_covers() -> None:
    digests = [(d, n, p) for d, n, p in fields() if n == "digest" or n.endswith("_digest")]
    assert len(digests) > 20
    for definition, name, prop in digests:
        of = annotated(prop, "x-digest-of")
        assert isinstance(of, dict), f"{definition}.{name} says nothing of what it covers"
        for entry in of.get("entries", []):
            if entry != ".":
                REE_TREE.at(*PurePosixPath(entry).parts)


def test_every_path_says_where_in_the_tree_it_is_resolved() -> None:
    paths = [(d, n, p) for d, n, p in fields() if n in ("path", "lfs_paths") or n.endswith(("_path", "_paths"))]
    assert len(paths) > 10
    for definition, name, prop in paths:
        roots = annotated(prop, "x-relative-to")
        assert isinstance(roots, list), f"{definition}.{name} says nothing of where it is resolved"
        assert roots
        for root in roots:
            assert root == "." or REE_TREE.at(root).kind == "directory"
