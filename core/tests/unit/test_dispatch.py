"""Dispatch coverage for ``operations.dispatch``.

Asserts every Command variant routes to its own handler and that an unknown
command hits the fallthrough. The handlers themselves are container-bound, so
they are replaced with a recorder — this test is about the routing table, not
the handlers' behaviour. The variants are constructed with ``model_construct``
(args bypass validation, since a stubbed handler never reads them), so adding a
command with required args does not need fixture upkeep here.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import BaseModel

from repo2ree_core.operations import dispatch as rc
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    ActivationTestCommand,
    BuildRuntimeCommand,
    Command,
    CrossCheckSbomCommand,
    DeleteFileCommand,
    EvaluateDependencyScoreCommand,
    ExtractUploadCommand,
    GenerateHbomCommand,
    GenerateSbomCommand,
    MaterializeWorkspaceCommand,
    PatchReeIntentCommand,
    PrepareSourceCommand,
    RemoveSourceCommand,
    ResetForSourceChangeCommand,
    ReviewAcquireSourceCommand,
    ReviewBuildRuntimeCommand,
    RunExperimentCommand,
    SealReeCommand,
    SnapshotUpstreamCommand,
    UpdateSourceMetadataCommand,
    WriteFileCommand,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

# (Command class, name of the handler in dispatch it must route to).
_ROUTES: list[tuple[type[BaseModel], str]] = [
    (AcquireSourceCommand, "handle_acquire_source"),
    (ReviewAcquireSourceCommand, "handle_review_acquire_source"),
    (ReviewBuildRuntimeCommand, "handle_review_build_runtime"),
    (SnapshotUpstreamCommand, "handle_snapshot_upstream"),
    (MaterializeWorkspaceCommand, "handle_materialize_workspace"),
    (UpdateSourceMetadataCommand, "handle_update_source_metadata"),
    (ExtractUploadCommand, "handle_extract_upload"),
    (WriteFileCommand, "handle_write_file"),
    (DeleteFileCommand, "handle_delete_file"),
    (PatchReeIntentCommand, "handle_patch_ree_intent"),
    (PrepareSourceCommand, "handle_prepare_source"),
    (RemoveSourceCommand, "handle_remove_source"),
    (ResetForSourceChangeCommand, "handle_reset_for_source_change"),
    (BuildRuntimeCommand, "handle_build_runtime"),
    (EvaluateDependencyScoreCommand, "handle_evaluate_dependency_score"),
    (RunExperimentCommand, "handle_run_experiment"),
    (GenerateHbomCommand, "handle_generate_hbom"),
    (GenerateSbomCommand, "handle_generate_sbom"),
    (CrossCheckSbomCommand, "handle_cross_check_sbom"),
    (ActivationTestCommand, "handle_activation_test"),
    (SealReeCommand, "handle_seal_ree"),
]

_ALL_HANDLERS = [name for _, name in _ROUTES]


def _null_log() -> LogSink:
    return lambda _stream, _level, _message: None


@pytest.mark.parametrize("command_cls,handler_name", _ROUTES, ids=lambda v: getattr(v, "__name__", v))
def test_routes_to_its_handler(
    command_cls: type[BaseModel], handler_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []

    def recorder(name: str) -> Any:
        def _handler(*_args: object, **_kwargs: object) -> ActionResult:
            called.append(name)
            return ActionResult(status="succeeded")

        return _handler

    for name in _ALL_HANDLERS:
        monkeypatch.setattr(rc, name, recorder(name))

    operation = command_cls.model_fields["operation"].default
    cmd = command_cls.model_construct(operation=operation, args=object())

    result = rc.run_command(cast(Command, cmd), log=_null_log(), is_canceled=lambda: False)

    assert result.status == "succeeded"
    assert called == [handler_name]


@pytest.mark.parametrize("command_cls,handler_name", _ROUTES, ids=lambda v: getattr(v, "__name__", v))
def test_cancel_before_start_never_reaches_the_handler(
    command_cls: type[BaseModel], handler_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-start cancel guard lives here, so it must hold for every command.

    It used to be re-implemented in each handler, which meant a new handler
    could silently omit it. Parametrized over the same routing table so a
    command added without a cancel-honouring path fails here.
    """
    called: list[str] = []

    for name in _ALL_HANDLERS:
        monkeypatch.setattr(rc, name, lambda *_a, _n=name, **_k: called.append(_n))

    operation = command_cls.model_fields["operation"].default
    cmd = command_cls.model_construct(operation=operation, args=object())

    result = rc.run_command(cast(Command, cmd), log=_null_log(), is_canceled=lambda: True)

    assert result.status == "canceled"
    assert called == []


def test_unknown_command_raises() -> None:
    bogus = SimpleNamespace(operation="not_a_real_operation")
    with pytest.raises(ValueError, match="Unhandled command operation"):
        rc.run_command(bogus, log=_null_log())  # type: ignore[arg-type]
