from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from repo2ree_protocol.command import Command
from repo2ree_protocol.outputs import OUTPUTS, validate_outputs
from repo2ree_protocol.result import ActionResult

OPERATIONS = {command.model_fields["operation"].default for command in get_args(get_args(Command)[0])}


def test_every_command_declares_its_outputs() -> None:
    assert set(OUTPUTS) == OPERATIONS


def test_a_success_must_carry_what_its_operation_declares() -> None:
    with pytest.raises(ValidationError):
        validate_outputs("seal_ree", ActionResult(status="succeeded"))


def test_a_failure_may_carry_nothing() -> None:
    validate_outputs("seal_ree", ActionResult.failed("execution", "it broke"))


def test_outputs_an_operation_does_not_declare_are_refused() -> None:
    with pytest.raises(ValidationError):
        validate_outputs("write_file", ActionResult(status="succeeded", outputs={"surprise": 1}))
