from __future__ import annotations

import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from repo2ree_protocol.command import SealReeArgs, SealReeCommand
from repo2ree_protocol.export_schema import MESSAGES, SCHEMA_PATH, schema_document
from repo2ree_protocol.outputs import OUTPUTS
from repo2ree_protocol.queries import QUERIES
from repo2ree_protocol.result import ActionResult

DOCUMENT = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validator(entry: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator({"$defs": DOCUMENT["$defs"], **entry})


def test_the_committed_schema_is_current() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_document(), "run: just generate-protocol-schema"


def test_the_schema_is_valid_and_indexes_everything_the_protocol_names() -> None:
    Draft202012Validator.check_schema(DOCUMENT)
    assert set(DOCUMENT["x-messages"]) == set(MESSAGES)
    assert set(DOCUMENT["x-outputs"]) == set(OUTPUTS)
    assert set(DOCUMENT["x-queries"]) == set(QUERIES)


@pytest.mark.parametrize(
    ("message", "instance"),
    [
        ("Command", SealReeCommand(args=SealReeArgs()).model_dump(mode="json")),
        ("ActionResult", ActionResult.failed("execution", "it broke").model_dump(mode="json")),
    ],
)
def test_a_message_the_protocol_writes_conforms(message: str, instance: dict[str, Any]) -> None:
    validator(DOCUMENT["x-messages"][message]).validate(instance)


def test_outputs_conform_per_operation() -> None:
    validator(DOCUMENT["x-outputs"]["write_file"]).validate({})
    assert not validator(DOCUMENT["x-outputs"]["write_file"]).is_valid({"surprise": 1})
