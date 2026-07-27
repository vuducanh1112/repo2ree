from __future__ import annotations

from typing import Never, NoReturn

from pydantic import BaseModel

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers.acquire_source import handle_acquire_source
from repo2ree_core.operations.handlers.activation_test import handle_activation_test
from repo2ree_core.operations.handlers.build_runtime import handle_build_runtime
from repo2ree_core.operations.handlers.cross_check_sbom import handle_cross_check_sbom
from repo2ree_core.operations.handlers.delete_file import handle_delete_file
from repo2ree_core.operations.handlers.evaluate_dependency_score import (
    handle_evaluate_dependency_score,
)
from repo2ree_core.operations.handlers.extract_upload import handle_extract_upload
from repo2ree_core.operations.handlers.generate_hbom import handle_generate_hbom
from repo2ree_core.operations.handlers.generate_sbom import handle_generate_sbom
from repo2ree_core.operations.handlers.generate_script_candidates import (
    handle_generate_script_candidates,
)
from repo2ree_core.operations.handlers.load_ree_bundle import handle_load_ree_bundle
from repo2ree_core.operations.handlers.materialize_workspace import (
    handle_materialize_workspace,
)
from repo2ree_core.operations.handlers.patch_ree_intent import handle_patch_ree_intent
from repo2ree_core.operations.handlers.prepare_source import handle_prepare_source
from repo2ree_core.operations.handlers.remove_source import handle_remove_source
from repo2ree_core.operations.handlers.review_acquire_source import handle_review_acquire_source
from repo2ree_core.operations.handlers.review_activation_test import handle_review_activation_test
from repo2ree_core.operations.handlers.review_build_runtime import handle_review_build_runtime
from repo2ree_core.operations.handlers.review_run_experiment import handle_review_run_experiment
from repo2ree_core.operations.handlers.run_experiment import handle_run_experiment
from repo2ree_core.operations.handlers.seal_ree import handle_seal_ree
from repo2ree_core.operations.handlers.snapshot_upstream import handle_snapshot_upstream
from repo2ree_core.operations.handlers.source_reset import handle_reset_for_source_change
from repo2ree_core.operations.handlers.update_source_metadata import (
    handle_update_source_metadata,
)
from repo2ree_core.operations.handlers.write_file import handle_write_file
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
    GenerateScriptCandidatesCommand,
    LoadReeBundleCommand,
    MaterializeWorkspaceCommand,
    PatchReeIntentCommand,
    PrepareSourceCommand,
    RemoveSourceCommand,
    ResetForSourceChangeCommand,
    ReviewAcquireSourceCommand,
    ReviewActivationTestCommand,
    ReviewBuildRuntimeCommand,
    ReviewRunExperimentCommand,
    RunExperimentCommand,
    SealReeCommand,
    SnapshotUpstreamCommand,
    UpdateSourceMetadataCommand,
    WriteFileCommand,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    get_tracer,
    record_command_status,
    record_exit_code,
    record_span_facts,
)

tracer = get_tracer(__name__)


def run_command(
    cmd: Command,
    *,
    log: LogSink,
    run_id: str = "manual",
    is_canceled: CancelCheck | None = None,
) -> ActionResult:
    """Dispatch a typed Command to its handler and return an ActionResult."""
    cancel: CancelCheck = is_canceled if is_canceled is not None else lambda: False
    with tracer.start_as_current_span(f"command.{cmd.operation}") as span:
        CommandSpanAttrs(operation=str(cmd.operation), run_id=run_id).apply(span)
        # The command span is the wide event for this unit of work: args go on
        # before dispatch so a failed or killed command still carries its
        # inputs; outputs (receipts, verdicts, digests) go on after. Accessed
        # defensively — observability must not be able to fail a command.
        args = getattr(cmd, "args", None)
        if isinstance(args, BaseModel):
            record_span_facts(span, args.model_dump(), namespace="arg")
        result = _dispatch(cmd, log=log, run_id=run_id, cancel=cancel)
        record_exit_code(span, result.exit_code)
        record_span_facts(span, result.outputs, namespace="output")
        record_command_status(span, result.status)
        return result


def _dispatch(
    cmd: Command,
    *,
    log: LogSink,
    run_id: str,
    cancel: CancelCheck,
) -> ActionResult:
    if isinstance(cmd, AcquireSourceCommand):
        return handle_acquire_source(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ReviewAcquireSourceCommand):
        return handle_review_acquire_source(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ReviewBuildRuntimeCommand):
        return handle_review_build_runtime(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ReviewActivationTestCommand):
        return handle_review_activation_test(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ReviewRunExperimentCommand):
        return handle_review_run_experiment(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, SnapshotUpstreamCommand):
        return handle_snapshot_upstream(run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, MaterializeWorkspaceCommand):
        return handle_materialize_workspace(log=log, is_canceled=cancel)
    if isinstance(cmd, UpdateSourceMetadataCommand):
        return handle_update_source_metadata(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, ExtractUploadCommand):
        return handle_extract_upload(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, LoadReeBundleCommand):
        return handle_load_ree_bundle(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, WriteFileCommand):
        return handle_write_file(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, DeleteFileCommand):
        return handle_delete_file(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, PatchReeIntentCommand):
        return handle_patch_ree_intent(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, PrepareSourceCommand):
        return handle_prepare_source(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, RemoveSourceCommand):
        return handle_remove_source(log=log, is_canceled=cancel)
    if isinstance(cmd, ResetForSourceChangeCommand):
        return handle_reset_for_source_change(log=log, is_canceled=cancel)
    if isinstance(cmd, BuildRuntimeCommand):
        return handle_build_runtime(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, EvaluateDependencyScoreCommand):
        return handle_evaluate_dependency_score(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, RunExperimentCommand):
        return handle_run_experiment(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, GenerateHbomCommand):
        return handle_generate_hbom(log=log, is_canceled=cancel)
    if isinstance(cmd, GenerateSbomCommand):
        return handle_generate_sbom(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, CrossCheckSbomCommand):
        return handle_cross_check_sbom(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ActivationTestCommand):
        return handle_activation_test(cmd.args, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, GenerateScriptCandidatesCommand):
        return handle_generate_script_candidates(cmd.args, log=log, is_canceled=cancel)
    if isinstance(cmd, SealReeCommand):
        return handle_seal_ree(cmd.args, log=log, is_canceled=cancel)
    return _unhandled_command(cmd)


def _unhandled_command(cmd: Never) -> NoReturn:
    """The dispatch fallthrough, reachable only for a non-``Command`` value.

    Typed to accept ``Never`` so it doubles as the exhaustiveness check: every
    member of the union must be dispatched above, or the call below fails to
    type-check naming the command nobody handled. A command added to ``Command``
    without a branch therefore fails the build rather than reaching a workbench
    and failing as an unhandled operation the type system had already promised
    was handleable.

    Preferred over a bare :func:`typing.assert_never`, which would raise
    ``AssertionError`` carrying only a repr. Commands arrive deserialized from
    the wire, so the fallthrough is worth keeping legible for whoever reads the
    run log when something malformed slips past validation.
    """
    raise ValueError(f"Unhandled command operation: {getattr(cmd, 'operation', cmd)!r}")
