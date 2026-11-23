from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from repo2ree_core.digests import digest_file, digest_output_paths
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.envelope import receipt_envelope
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, run_runnable
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.launch import Launch, declared_launch
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.working_environment import observe_working_environment
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms
from repo2ree_core.workspace.attempt import discard, lay_out
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import RunnableOperationOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import Digest
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    ExperimentDefinition,
    Ree,
)
from repo2ree_ree.primitives import ExperimentEnvironmentPath
from repo2ree_ree.receipt import ActivateExperimentEnvironmentReceipt, Launched, RunExperimentReceipt
from repo2ree_ree.working_environment import WorkingEnvironmentObservation

RunnableKind = Literal["activate_experiment_environment", "run_experiment"]
RunnableDefinition = ActivateExperimentEnvironmentDefinition | ExperimentDefinition


def handle_runnable_operation(
    kind: RunnableKind,
    *,
    layout: ReeLayout,
    experiment_name: str = "",
    again: bool = False,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "no REE here: run `ree initialize-ree` first")

    try:
        ree = load_ree(layout, store)
        definition = _select_definition(ree, kind, experiment_name)
        if not again and (current := _current_receipt(ree, definition)) is not None:
            return _already_current(definition, current, log)
        experiment_environment_path, experiment_environment_digest = _check_preconditions(ree, definition)
        workspace = lay_out(layout, ree, run_id, environment=True)
        activation = _check_activation(ree, workspace)
        if isinstance(definition, ExperimentDefinition):
            _check_experiment_scripts(definition, workspace)
        launch = declared_launch(ree.subject.definition.launch, workspace)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot {kind}: {exc}")
        return ActionResult.failed("precondition", f"cannot {kind}: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load {kind} inputs: {exc}")

    before_revision = revision_of(ree)
    runnable = _as_runnable(definition, activation, launch)
    label = definition.name if isinstance(definition, ExperimentDefinition) else "activation"
    timer = OperationTimer.start()
    outcome = run_runnable(
        workspace=workspace,
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = _outputs(outcome, experiment_environment_path)
    if outcome.status == "canceled":
        log("system", "warn", f"{kind} canceled")
        return ActionResult(status="canceled", outputs=outputs.model_dump(mode="json", exclude_none=True))
    if outcome.status != "succeeded":
        exit_code = outcome.run_outputs.verify_exit_code or outcome.run_outputs.exit_code or 1
        log("system", "error", f"{kind} failed with exit code {exit_code}")
        return ActionResult.failed(
            "execution",
            f"{kind} failed",
            exit_code=exit_code,
            outputs=outputs.model_dump(mode="json", exclude_none=True),
        )
    expected_verify = isinstance(definition, ExperimentDefinition)
    if outcome.run_outputs.exit_code != 0 or (outcome.run_outputs.verify_exit_code == 0) != expected_verify:
        message = f"{kind} reported success without complete successful script outcomes"
        log("system", "error", message)
        return ActionResult.failed("internal", message)

    produced_output_digest: Digest | None = None
    if isinstance(definition, ExperimentDefinition) and definition.output_paths:
        try:
            produced_output_digest = _capture_experiment_outputs(layout, workspace, definition, log)
        except Exception as exc:
            return failed_from_exception(exc, f"failed to capture experiment outputs: {exc}")

    timing = timer.finish()
    receipt = _successful_receipt(
        definition,
        run_id=run_id,
        timing=timing,
        snapshot_digest=_source_snapshot(ree),
        experiment_environment_path=experiment_environment_path,
        experiment_environment_digest=experiment_environment_digest,
        produced_output_digest=produced_output_digest,
        activate_experiment_environment_script_digest=activation.activate_experiment_environment_script_digest,
        working_environment=observe_working_environment(),
        launch_script_digest=_launch_digest(ree),
        launched=outcome.launched,
    )
    try:
        save_ree(
            layout,
            store,
            commit_receipt(ree, receipt),
            expected_revision=before_revision,
        )
    except ReeRevisionConflictError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        log("system", "error", f"failed to commit {kind} receipt: {exc}")
        return failed_from_exception(exc, f"failed to commit {kind} receipt: {exc}")

    outputs.receipt = receipt
    discard(layout, run_id)
    log(
        "system",
        "info",
        f"{kind} succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=outputs.model_dump(mode="json", exclude_none=True),
    )


def _current_receipt(
    ree: Ree, definition: RunnableDefinition
) -> ActivateExperimentEnvironmentReceipt | RunExperimentReceipt | None:
    audited = audit(ree)
    if isinstance(definition, ExperimentDefinition):
        step = next((item.run for item in audited.experiments if item.name == definition.name), None)
        receipt: ActivateExperimentEnvironmentReceipt | RunExperimentReceipt | None = (
            ree.subject.receipts.experiments.get(definition.name)
        )
    else:
        step, receipt = audited.activate_experiment_environment, ree.subject.receipts.activate_experiment_environment
    return receipt if receipt is not None and step is not None and step.evidence == "current" else None


def _already_current(
    definition: RunnableDefinition,
    receipt: ActivateExperimentEnvironmentReceipt | RunExperimentReceipt,
    log: LogSink,
) -> ActionResult:
    experiment = isinstance(definition, ExperimentDefinition)
    label = definition.name if isinstance(definition, ExperimentDefinition) else "activation"
    log("system", "info", f"{label} is current: nothing to do (--again runs it anyway)")
    outputs = RunnableOperationOutputs(
        subject_name=label,
        exit_code=0,
        verify_exit_code=0 if experiment else None,
        verdict="pass" if experiment else None,
        experiment_environment_path=str(getattr(receipt, "experiment_environment_path", None) or ""),
        receipt=receipt,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json", exclude_none=True))


def _select_definition(ree: Ree, kind: RunnableKind, experiment_name: str) -> RunnableDefinition:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot run author operations")
    if kind == "activate_experiment_environment":
        return ree.subject.definition.activate_experiment_environment
    for experiment in ree.subject.definition.experiments:
        if experiment.name == experiment_name:
            return experiment
    raise ReePreconditionError(f"experiment {experiment_name!r} is not defined")


def _check_preconditions(
    ree: Ree, definition: RunnableDefinition
) -> tuple[ExperimentEnvironmentPath | None, Digest | None]:
    if ree.subject.receipts.acquire_source is None:
        raise ReePreconditionError("source has not been acquired")
    if isinstance(definition, ExperimentDefinition):
        _check_activation_evidence(ree)
    experiment_environment = ree.subject.definition.experiment_environment
    if experiment_environment.artifact_path is None:
        return None, None
    build = ree.subject.receipts.build_experiment_environment
    if build is None:
        raise ReePreconditionError("experiment environment has not been built")
    experiment_environment_audit = audit(ree).build_experiment_environment
    if experiment_environment_audit.evidence != "current":
        detail = "; ".join(experiment_environment_audit.reasons) or "build evidence is not current"
        raise ReePreconditionError(detail)
    return experiment_environment.artifact_path, build.produced_artifact_digest


def _check_experiment_scripts(definition: ExperimentDefinition, workspace: Path) -> None:
    _check_script(
        workspace / str(definition.run_script_path),
        definition.run_script_digest,
        definition.run_script_size,
        label="run script",
    )
    _check_script(
        workspace / str(definition.verify_script_path),
        definition.verify_script_digest,
        definition.verify_script_size,
        label="verification script",
    )


def _check_activation_evidence(ree: Ree) -> None:
    activation_audit = audit(ree).activate_experiment_environment
    if activation_audit.evidence != "current":
        raise ReePreconditionError("; ".join(activation_audit.reasons) or "the activation has not been tested")


def _check_script(path: Path, expected_digest: Digest, expected_size: int, *, label: str) -> None:
    if not path.is_file():
        raise ReePreconditionError(f"the {label} is missing")
    if digest_file(path) != expected_digest or path.stat().st_size != expected_size:
        raise ReePreconditionError(f"the {label} does not match its definition")


def _check_activation(ree: Ree, workspace: Path) -> ActivateExperimentEnvironmentDefinition:
    activation = ree.subject.definition.activate_experiment_environment
    _check_script(
        workspace / str(activation.activate_experiment_environment_script_path),
        activation.activate_experiment_environment_script_digest,
        activation.activate_experiment_environment_script_size,
        label="activate experiment environment script",
    )
    return activation


def _as_runnable(
    definition: RunnableDefinition, activation: ActivateExperimentEnvironmentDefinition, launch: Launch | None
) -> RunnableSpec:
    activate_script = str(activation.activate_experiment_environment_script_path)
    if not isinstance(definition, ExperimentDefinition):
        return RunnableSpec(activate_script=activate_script, launch=launch)
    return RunnableSpec(
        activate_script=activate_script,
        launch=launch,
        run_script=str(definition.run_script_path),
        verify_script=str(definition.verify_script_path),
        output_paths=tuple(str(path) for path in definition.output_paths),
    )


def _outputs(
    outcome: ExperimentRunOutcome, experiment_environment_path: ExperimentEnvironmentPath | None
) -> RunnableOperationOutputs:
    return RunnableOperationOutputs(
        **outcome.run_outputs.model_dump(),
        experiment_environment_path=str(experiment_environment_path or ""),
    )


def _launch_digest(ree: Ree) -> Digest:
    return ree.subject.definition.launch.launch_script_digest


def _source_snapshot(ree: Ree) -> Digest:
    source = ree.subject.receipts.acquire_source
    if source is None:
        raise AssertionError("runnable preconditions admitted a REE without source evidence")
    return source.snapshot_digest


def _successful_receipt(
    definition: RunnableDefinition,
    *,
    run_id: str,
    timing: OperationTiming,
    snapshot_digest: Digest,
    experiment_environment_path: ExperimentEnvironmentPath | None,
    experiment_environment_digest: Digest | None,
    produced_output_digest: Digest | None,
    activate_experiment_environment_script_digest: Digest,
    working_environment: WorkingEnvironmentObservation,
    launch_script_digest: Digest,
    launched: Launched | None,
) -> ActivateExperimentEnvironmentReceipt | RunExperimentReceipt:
    envelope = receipt_envelope(run_id, timing)
    if not isinstance(definition, ExperimentDefinition):
        return ActivateExperimentEnvironmentReceipt(
            **envelope,
            snapshot_digest=snapshot_digest,
            experiment_environment_path=experiment_environment_path,
            experiment_environment_digest=experiment_environment_digest,
            activate_experiment_environment_script_digest=activate_experiment_environment_script_digest,
            exit_code=0,
            working_environment=working_environment,
            launch_script_digest=launch_script_digest,
            launched=launched,
        )
    return RunExperimentReceipt(
        **envelope,
        experiment_name=definition.name,
        snapshot_digest=snapshot_digest,
        experiment_environment_digest=experiment_environment_digest,
        activate_experiment_environment_script_digest=activate_experiment_environment_script_digest,
        run_script_digest=definition.run_script_digest,
        verify_script_digest=definition.verify_script_digest,
        run_exit_code=0,
        verify_exit_code=0,
        produced_output_digest=produced_output_digest,
        working_environment=working_environment,
        launch_script_digest=launch_script_digest,
        launched=launched,
    )


def _capture_experiment_outputs(
    layout: ReeLayout,
    workspace: Path,
    definition: ExperimentDefinition,
    log: LogSink,
) -> Digest:
    output_paths = [str(path) for path in definition.output_paths]
    result_store = layout.results_dir(definition.name)
    if result_store.exists():
        shutil.rmtree(result_store)
    for relative in output_paths:
        source = workspace / relative
        if source.is_dir():
            shutil.copytree(source, result_store / relative, dirs_exist_ok=True)
        elif source.is_file():
            destination = result_store / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        else:
            log("system", "warn", f"declared output not found, skipping capture: {relative}")
    digest = digest_output_paths(workspace, output_paths)
    if digest is None:
        raise AssertionError("declared experiment outputs produced no digest")
    return digest
