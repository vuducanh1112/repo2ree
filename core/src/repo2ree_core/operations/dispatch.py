from __future__ import annotations

from typing import Never, NoReturn
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.capture import capture_command
from repo2ree_core.operations.handlers.author.acquire_source import handle_acquire_source
from repo2ree_core.operations.handlers.author.activate_experiment_environment import (
    handle_activate_experiment_environment,
)
from repo2ree_core.operations.handlers.author.build_experiment_environment import handle_build_experiment_environment
from repo2ree_core.operations.handlers.author.check_working_environment import handle_check_working_environment
from repo2ree_core.operations.handlers.author.cross_check_sbom import handle_cross_check_sbom
from repo2ree_core.operations.handlers.author.evaluate_reproducibility import (
    handle_evaluate_reproducibility,
)
from repo2ree_core.operations.handlers.author.generate_sbom import handle_generate_sbom
from repo2ree_core.operations.handlers.author.lint_scripts import handle_lint_scripts
from repo2ree_core.operations.handlers.author.load_ree_bundle import handle_load_ree_bundle
from repo2ree_core.operations.handlers.author.materialize_workspace import (
    handle_materialize_workspace,
)
from repo2ree_core.operations.handlers.author.observe_hardware import handle_observe_hardware
from repo2ree_core.operations.handlers.author.patch_ree_definition import handle_patch_ree_definition
from repo2ree_core.operations.handlers.author.remove_source import handle_remove_source
from repo2ree_core.operations.handlers.author.run_experiment import handle_run_experiment
from repo2ree_core.operations.handlers.author.seal_ree import handle_seal_ree
from repo2ree_core.operations.handlers.author.sign_ree import handle_sign_ree
from repo2ree_core.operations.handlers.author.suggest_scripts import (
    handle_suggest_scripts,
)
from repo2ree_core.operations.handlers.author.write_script import handle_write_script
from repo2ree_core.operations.handlers.review.acquire_source import handle_review_acquire_source
from repo2ree_core.operations.handlers.review.activate_experiment_environment import (
    handle_review_activate_experiment_environment,
)
from repo2ree_core.operations.handlers.review.build_experiment_environment import (
    handle_review_build_experiment_environment,
)
from repo2ree_core.operations.handlers.review.run_experiment import handle_review_run_experiment
from repo2ree_core.operations.handlers.review.sign_review import handle_sign_review
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    ActivateExperimentEnvironmentCommand,
    BuildExperimentEnvironmentCommand,
    CheckWorkingEnvironmentCommand,
    Command,
    CrossCheckSbomCommand,
    EvaluateReproducibilityCommand,
    GenerateSbomCommand,
    LintScriptsCommand,
    LoadReeBundleCommand,
    MaterializeWorkspaceCommand,
    ObserveHardwareCommand,
    PatchReeDefinitionCommand,
    RemoveSourceCommand,
    ReviewAcquireSourceCommand,
    ReviewActivateExperimentEnvironmentCommand,
    ReviewBuildExperimentEnvironmentCommand,
    ReviewRunExperimentCommand,
    RunExperimentCommand,
    SealReeCommand,
    SignReeCommand,
    SignReviewCommand,
    SuggestScriptsCommand,
    WriteScriptCommand,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import validate_outputs
from repo2ree_protocol.result import ActionResult
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import (
    CommandSpanAttrs,
    record_command_status,
    record_exit_code,
    record_failure,
    record_result_evidence,
    record_span_facts,
)

tracer = get_tracer(__name__)


def run_command(
    cmd: Command,
    *,
    layout: ReeLayout,
    log: LogSink,
    run_id: str | None = None,
    is_canceled: CancelCheck | None = None,
    context: ExecutionContext | None = None,
    records_edit: str | None = None,
) -> ActionResult:
    context = context or ExecutionContext.new()
    resolved_run_id = run_id or f"manual-{uuid4().hex[:12]}"
    cancel: CancelCheck = is_canceled if is_canceled is not None else lambda: False
    with tracer.start_as_current_span(f"command.{cmd.operation}") as span:
        CommandSpanAttrs(operation=str(cmd.operation), run_id=resolved_run_id, execution=context).apply(span)
        args = getattr(cmd, "args", None)
        if isinstance(args, BaseModel):
            record_span_facts(span, args.model_dump(), namespace="arg")
        result = capture_command(
            context=context,
            layout=layout,
            cmd=cmd,
            run_id=resolved_run_id,
            log=log,
            execute=lambda staged: _run_unless_canceled(
                cmd, layout=staged, log=log, run_id=resolved_run_id, cancel=cancel
            ),
            records_edit=records_edit,
        )
        result = result.model_copy(update={"context": context})
        try:
            validate_outputs(cmd.operation, result)
        except ValidationError as exc:
            result = ActionResult.failed(
                "internal", f"{cmd.operation} returned outputs the protocol does not declare: {exc}"
            ).model_copy(update={"context": context})
        record_exit_code(span, result.exit_code)
        record_span_facts(span, result.outputs, namespace="output")
        record_failure(span, result.failure)
        record_command_status(span, result.status)
        record_result_evidence(span, result)
        return result


def _run_unless_canceled(
    cmd: Command,
    *,
    layout: ReeLayout,
    log: LogSink,
    run_id: str,
    cancel: CancelCheck,
) -> ActionResult:
    if cancel():
        log("system", "warn", f"{cmd.operation} canceled before start")
        return ActionResult(status="canceled")
    return _dispatch(cmd, layout=layout, log=log, run_id=run_id, cancel=cancel)


def _dispatch(
    cmd: Command,
    *,
    layout: ReeLayout,
    log: LogSink,
    run_id: str,
    cancel: CancelCheck,
) -> ActionResult:
    if isinstance(cmd, ReviewAcquireSourceCommand):
        return handle_review_acquire_source(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ReviewBuildExperimentEnvironmentCommand):
        return handle_review_build_experiment_environment(
            cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel
        )
    if isinstance(cmd, ReviewActivateExperimentEnvironmentCommand):
        return handle_review_activate_experiment_environment(
            cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel
        )
    if isinstance(cmd, ReviewRunExperimentCommand):
        return handle_review_run_experiment(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, MaterializeWorkspaceCommand):
        return handle_materialize_workspace(layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, LoadReeBundleCommand):
        return handle_load_ree_bundle(cmd.args, layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, SignReeCommand):
        return handle_sign_ree(cmd.args, layout=layout, log=log)
    if isinstance(cmd, SignReviewCommand):
        return handle_sign_review(cmd.args, layout=layout, log=log)
    if isinstance(cmd, WriteScriptCommand):
        return handle_write_script(cmd.args, layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, PatchReeDefinitionCommand):
        return handle_patch_ree_definition(cmd.args, layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, AcquireSourceCommand):
        return handle_acquire_source(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, RemoveSourceCommand):
        return handle_remove_source(layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, BuildExperimentEnvironmentCommand):
        return handle_build_experiment_environment(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, EvaluateReproducibilityCommand):
        return handle_evaluate_reproducibility(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, RunExperimentCommand):
        return handle_run_experiment(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ObserveHardwareCommand):
        return handle_observe_hardware(layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, GenerateSbomCommand):
        return handle_generate_sbom(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, CrossCheckSbomCommand):
        return handle_cross_check_sbom(layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, ActivateExperimentEnvironmentCommand):
        return handle_activate_experiment_environment(
            cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel
        )
    if isinstance(cmd, CheckWorkingEnvironmentCommand):
        return handle_check_working_environment(cmd.args, layout=layout, run_id=run_id, log=log, is_canceled=cancel)
    if isinstance(cmd, SuggestScriptsCommand):
        return handle_suggest_scripts(cmd.args, layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, LintScriptsCommand):
        return handle_lint_scripts(cmd.args, layout=layout, log=log, is_canceled=cancel)
    if isinstance(cmd, SealReeCommand):
        return handle_seal_ree(cmd.args, layout=layout, log=log, is_canceled=cancel)
    return _unhandled_command(cmd)


def _unhandled_command(cmd: Never) -> NoReturn:
    raise ValueError(f"Unhandled command operation: {getattr(cmd, 'operation', cmd)!r}")
