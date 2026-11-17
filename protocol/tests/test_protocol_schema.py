from __future__ import annotations

import json
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from repo2ree_protocol.command import SealReeArgs, SealReeCommand
from repo2ree_protocol.export_schema import MESSAGES, schema_document
from repo2ree_protocol.outputs import OUTPUTS
from repo2ree_protocol.queries import REPLIES, query_types, verb_of
from repo2ree_protocol.result import ActionResult

DOCUMENT = json.loads(schema_document())


def validator(entry: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator({"$defs": DOCUMENT["$defs"], **entry})


def test_the_schema_is_valid_and_indexes_everything_the_protocol_names() -> None:
    Draft202012Validator.check_schema(DOCUMENT)
    assert set(DOCUMENT["x-messages"]) == set(MESSAGES)
    assert set(DOCUMENT["x-outputs"]) == set(OUTPUTS)
    assert set(DOCUMENT["x-queries"]) == {verb_of(query) for query in REPLIES}
    assert set(REPLIES) == set(query_types())


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
    validator(DOCUMENT["x-outputs"]["write_script"]).validate({})
    assert not validator(DOCUMENT["x-outputs"]["write_script"]).is_valid({"surprise": 1})
