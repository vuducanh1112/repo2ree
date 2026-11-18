"""The author's check of the working environment: run there before the scripts, recorded, and carried by the seal."""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import (
    CheckWorkingEnvironmentCommand,
    Command,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    RemoveSourceCommand,
    WriteScriptArgs,
    WriteScriptCommand,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.reserved_paths import RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT

PASSES = '#!/usr/bin/env sh\nset -eu\necho "checked in $(pwd)"\n'
FAILS = '#!/usr/bin/env sh\nset -eu\necho "cuda is missing" >&2\nexit 1\n'


def _run(layout: ReeLayout, command: Command) -> ActionResult:
    return run_command(command, log=lambda *_: None, layout=layout)


def _declared(tmp_path: Path, body: str = PASSES) -> ReeLayout:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="checked")
    written = _run(
        layout, WriteScriptCommand(args=WriteScriptArgs(path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, content=body))
    )
    assert written.status == "succeeded", written
    declared = _run(
        layout, PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"check_working_environment": {}}))
    )
    assert declared.status == "succeeded", declared
    return layout


def _check(layout: ReeLayout) -> ActionResult:
    return _run(layout, CheckWorkingEnvironmentCommand())


def test_a_passing_check_is_recorded_where_it_ran_and_completes_its_step(tmp_path: Path) -> None:
    layout = _declared(tmp_path)
    ree = ReeDirectory(layout).read_ree()
    assert audit(ree).check_working_environment.evidence == "missing"

    result = _check(layout)

    assert result.status == "succeeded", result
    ree = ReeDirectory(layout).read_ree()
    receipt = ree.subject.receipts.check_working_environment
    assert receipt is not None
    assert receipt.working_environment.host.arch
    assert receipt.check_working_environment_script_digest == (
        ree.subject.definition.check_working_environment.check_working_environment_script_digest
    )
    steps = {step.key: step.status for step in ree_steps(ree, audit(ree)).steps}
    assert steps["check_working_environment"] == "complete"


def test_a_failing_check_records_nothing_and_says_why(tmp_path: Path) -> None:
    layout = _declared(tmp_path, FAILS)
    lines: list[str] = []

    result = run_command(
        CheckWorkingEnvironmentCommand(),
        log=lambda _stream, _level, message: lines.append(message),
        layout=layout,
    )

    assert result.status == "failed"
    assert result.exit_code == 1
    assert "cuda is missing" in "\n".join(lines)
    assert ReeDirectory(layout).read_ree().subject.receipts.check_working_environment is None


def test_every_ree_starts_with_a_check_that_passes_and_its_step_still_to_do(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="fresh")
    ree = ReeDirectory(layout).read_ree()
    assert ree.subject.definition.check_working_environment is not None
    assert audit(ree).check_working_environment.evidence == "missing"
    assert {step.key: step.status for step in ree_steps(ree, audit(ree)).steps}["check_working_environment"] == "ready"

    assert _check(layout).status == "succeeded"


def test_editing_the_check_leaves_it_stale_and_removing_the_source_keeps_it(tmp_path: Path) -> None:
    layout = _declared(tmp_path)
    assert _check(layout).status == "succeeded"

    assert _run(layout, RemoveSourceCommand()).status in ("succeeded", "failed")
    assert ReeDirectory(layout).read_ree().subject.receipts.check_working_environment is not None

    edited = PASSES + "command -v sh >/dev/null\n"
    _run(
        layout, WriteScriptCommand(args=WriteScriptArgs(path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, content=edited))
    )
    ree = ReeDirectory(layout).read_ree()
    assert audit(ree).check_working_environment.reasons == ("check script changed",)


def test_the_declared_check_cannot_be_undeclared(tmp_path: Path) -> None:
    layout = _declared(tmp_path)

    result = _run(
        layout, PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"check_working_environment": None}))
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert "every REE declares check_working_environment" in result.failure.message
    assert ReeDirectory(layout).read_ree().subject.definition.check_working_environment is not None
