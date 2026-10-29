from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from repo2ree_ree.export_schema import SCHEMA_PATH, schema_document

SEALED = sorted((SCHEMA_PATH.parent / "sealed").glob("*.json"))


def test_the_committed_schema_is_current() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_document(), "run: just generate-ree-schema"


@pytest.mark.parametrize("path", SEALED, ids=lambda path: path.stem)
def test_a_sealed_document_conforms_to_the_schema(path: Path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(path.read_text(encoding="utf-8")))
