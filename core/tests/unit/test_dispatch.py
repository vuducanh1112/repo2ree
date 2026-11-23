from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import BaseModel

from repo2ree_core.operations import dispatch as rc
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    ActivateExperimentEnvironmentCommand,
    BuildExperimentEnvironmentCommand,
    Command,
    CrossCheckSbomCommand,
    EvaluateReproducibilityCommand,
    GenerateSbomCommand,
    MaterializeWorkspaceCommand,
    ObserveHardwareCommand,
    PatchReeDefinitionCommand,
    RemoveSourceCommand,
    ReviewAcquireSourceCommand,
    ReviewBuildExperimentEnvironmentCommand,
    RunExperimentCommand,
    SealReeCommand,
    WriteScriptCommand,
)
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.primitives import RunId

_ROUTES: list[tuple[type[BaseModel], str]] = [
    (AcquireSourceCommand, "handle_acquire_source"),
    (ReviewAcquireSourceCommand, "handle_review_acquire_source"),
    (ReviewBuildExperimentEnvironmentCommand, "handle_review_build_experiment_environment"),
    (MaterializeWorkspaceCommand, "handle_materialize_workspace"),
    (WriteScriptCommand, "handle_write_script"),
    (PatchReeDefinitionCommand, "handle_patch_ree_definition"),
    (RemoveSourceCommand, "handle_remove_source"),
    (BuildExperimentEnvironmentCommand, "handle_build_experiment_environment"),
    (EvaluateReproducibilityCommand, "handle_evaluate_reproducibility"),
    (RunExperimentCommand, "handle_run_experiment"),
    (ObserveHardwareCommand, "handle_observe_hardware"),
    (GenerateSbomCommand, "handle_generate_sbom"),
    (CrossCheckSbomCommand, "handle_cross_check_sbom"),
    (ActivateExperimentEnvironmentCommand, "handle_activate_experiment_environment"),
    (SealReeCommand, "handle_seal_ree"),
]

_ALL_HANDLERS = [name for _, name in _ROUTES]
_NO_REE = ReeLayout(root=Path("/nonexistent-ree"))


def _null_log() -> LogSink:
    return lambda _stream, _level, _message: None


@pytest.mark.parametrize(("command_cls", "handler_name"), _ROUTES, ids=lambda v: getattr(v, "__name__", v))
def test_routes_to_its_handler(
    command_cls: type[BaseModel], handler_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []
    monkeypatch.setattr(rc, "validate_outputs", lambda *_args: None)

    def recorder(name: str) -> Any:
        def _handler(*_args: object, **_kwargs: object) -> ActionResult:
            called.append(name)
            return ActionResult(status="succeeded")

        return _handler

    for name in _ALL_HANDLERS:
        monkeypatch.setattr(rc, name, recorder(name))

    operation = command_cls.model_fields["operation"].default
    cmd = command_cls.model_construct(operation=operation, args=object())

    result = rc.run_command(cast(Command, cmd), log=_null_log(), is_canceled=lambda: False, layout=_NO_REE)

    assert result.status == "succeeded"
    assert called == [handler_name]


@pytest.mark.parametrize(("command_cls", "handler_name"), _ROUTES, ids=lambda v: getattr(v, "__name__", v))
def test_cancel_before_start_never_reaches_the_handler(
    command_cls: type[BaseModel], handler_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []

    for name in _ALL_HANDLERS:
        monkeypatch.setattr(rc, name, lambda *_a, _n=name, **_k: called.append(_n))

    operation = command_cls.model_fields["operation"].default
    cmd = command_cls.model_construct(operation=operation, args=object())

    result = rc.run_command(cast(Command, cmd), log=_null_log(), is_canceled=lambda: True, layout=_NO_REE)

    assert result.status == "canceled"
    assert called == []


def test_unknown_command_raises() -> None:
    bogus = SimpleNamespace(operation="not_a_real_operation")
    with pytest.raises(ValueError, match="Unhandled command operation"):
        rc.run_command(bogus, log=_null_log(), layout=_NO_REE)  # type: ignore[arg-type]


def _run_id_seen_by_handler(monkeypatch: pytest.MonkeyPatch, run_id: str | None) -> str:
    seen: list[str] = []

    def _recorder(*_a: Any, run_id: str = "", **_k: Any) -> ActionResult:
        seen.append(run_id)
        return ActionResult(status="succeeded")

    for name in _ALL_HANDLERS:
        monkeypatch.setattr(rc, name, _recorder)

    cmd = BuildExperimentEnvironmentCommand.model_construct(operation="build_experiment_environment", args=object())
    rc.run_command(cast(Command, cmd), log=_null_log(), run_id=run_id, layout=_NO_REE)
    return seen[0]


def test_a_supplied_run_id_reaches_the_handler_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run_id_seen_by_handler(monkeypatch, "build-7") == "build-7"
    assert _run_id_seen_by_handler(monkeypatch, "manual") == "manual"


def test_an_absent_run_id_is_minted_once_before_the_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _run_id_seen_by_handler(monkeypatch, None)
    second = _run_id_seen_by_handler(monkeypatch, None)

    assert first.startswith("manual-")
    assert first != second
    assert RunId(first) == first
