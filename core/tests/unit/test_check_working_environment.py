"""The author's check of the working environment: run there before the scripts, recorded, and carried by the seal."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import ree_steps
from repo2ree_core.execution.working_environment import HOST_MACHINE, Machine
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import (
    CheckWorkingEnvironmentCommand,
    Command,
    DeleteFileArgs,
    DeleteFileCommand,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    RemoveSourceCommand,
    SealReeArgs,
    SealReeCommand,
    WriteFileArgs,
    WriteFileCommand,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.reserved_paths import RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT

PASSES = '#!/usr/bin/env sh\nset -eu\necho "checked in $(pwd)"\n'
FAILS = '#!/usr/bin/env sh\nset -eu\necho "cuda is missing" >&2\nexit 1\n'


def _run(layout: ReeLayout, command: Command, machine: Machine = HOST_MACHINE) -> ActionResult:
    return run_command(command, log=lambda *_: None, layout=layout, machine=machine)


def _declared(tmp_path: Path, body: str = PASSES) -> ReeLayout:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="checked")
    written = _run(
        layout, WriteFileCommand(args=WriteFileArgs(path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, content=body))
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
    assert audit(ree).working_environment_check.evidence == "missing"

    result = _check(layout)

    assert result.status == "succeeded", result
    ree = ReeDirectory(layout).read_ree()
    receipt = ree.subject.receipts.working_environment_check
    assert receipt is not None
    assert receipt.working_environment.backend == "host"
    assert receipt.check_working_environment_script_digest == (
        ree.subject.definition.check_working_environment.check_working_environment_script_digest  # type: ignore[union-attr]
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
        machine=HOST_MACHINE,
    )

    assert result.status == "failed"
    assert result.exit_code == 1
    assert "cuda is missing" in "\n".join(lines)
    assert ReeDirectory(layout).read_ree().subject.receipts.working_environment_check is None


def test_every_ree_starts_with_a_check_that_passes_and_its_step_still_to_do(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="fresh")
    ree = ReeDirectory(layout).read_ree()
    assert ree.subject.definition.check_working_environment is not None
    assert audit(ree).working_environment_check.evidence == "missing"
    assert {step.key: step.status for step in ree_steps(ree, audit(ree)).steps}["check_working_environment"] == "ready"

    assert _check(layout).status == "succeeded"


def test_an_undeclared_check_is_refused(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="unchecked")
    undeclared = _run(
        layout, PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"check_working_environment": None}))
    )
    assert undeclared.status == "succeeded", undeclared

    result = _check(layout)

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"
    ree = ReeDirectory(layout).read_ree()
    assert audit(ree).working_environment_check.evidence == "not_applicable"


def test_editing_the_check_leaves_it_stale_and_removing_the_source_keeps_it(tmp_path: Path) -> None:
    layout = _declared(tmp_path)
    assert _check(layout).status == "succeeded"

    assert _run(layout, RemoveSourceCommand()).status in ("succeeded", "failed")
    assert ReeDirectory(layout).read_ree().subject.receipts.working_environment_check is not None

    edited = PASSES + "command -v sh >/dev/null\n"
    _run(layout, WriteFileCommand(args=WriteFileArgs(path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, content=edited)))
    ree = ReeDirectory(layout).read_ree()
    assert audit(ree).working_environment_check.reasons == ("check script changed",)


def test_the_declared_check_cannot_be_deleted(tmp_path: Path) -> None:
    layout = _declared(tmp_path)

    result = _run(layout, DeleteFileCommand(args=DeleteFileArgs(path=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT)))

    assert result.status == "failed"
    assert result.failure is not None
    assert "undeclare the check" in result.failure.message


def _fake_docker(directory: Path) -> None:
    """A docker that knows one image, and saves it as a file."""
    directory.mkdir()
    engine = directory / "docker"
    engine.write_text(
        "#!/bin/sh\n"
        'case "$1 $2" in\n'
        f'  "image inspect") echo "sha256:{"a" * 64} python@sha256:{"b" * 64}" ;;\n'
        '  "tag "*) ;;\n'
        '  "save -o") echo image > "$3" ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    engine.chmod(engine.stat().st_mode | stat.S_IXUSR)


def test_the_seal_carries_the_working_environments_image_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_docker(tmp_path / "bin")
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}:{os.environ['PATH']}")
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="sealed", working_environment="container")
    declared = _run(
        layout,
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"working_environment": {"oci": "python:3.12"}})),
    )
    assert declared.status == "succeeded", declared

    sealed = _run(layout, SealReeCommand(args=SealReeArgs(working_environment_included=True)), Machine())

    assert sealed.status == "succeeded", sealed
    ree = ReeDirectory(layout).read_ree()
    assert "working-environment.tar" in {str(entry.path) for entry in ree.subject.contents.entries}
    with materialized_ree_download(layout) as archive:
        assert archive.stat().st_size > 0


def test_a_host_ree_has_no_image_to_include(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="host")

    sealed = _run(layout, SealReeCommand(args=SealReeArgs(working_environment_included=True)))

    assert sealed.status == "failed"
    assert sealed.failure is not None
    assert "declares no working environment" in sealed.failure.message
