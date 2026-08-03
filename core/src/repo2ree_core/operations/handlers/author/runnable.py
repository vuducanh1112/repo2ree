"""Shared direct workflow for successful activation and experiment evidence."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import Digest, digest_file, digest_output_paths
from repo2ree_core.domain.primitives import WorkspacePath
from repo2ree_core.domain.ree.assessment import assess
from repo2ree_core.domain.ree.model import ExperimentDefinition, Ree, TestActivationDefinition
from repo2ree_core.domain.ree.receipt import (
    RunExperimentReceipt,
    TestActivationReceipt,
    receipt_envelope,
)
from repo2ree_core.domain.ree.transitions import ReePreconditionError, commit_receipt, revision_of
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, run_runnable
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

RunnableKind = Literal["test_activation", "run_experiment"]
RunnableDefinition = TestActivationDefinition | ExperimentDefinition


class RunnableOperationOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_name: str
    exit_code: int | None = None
    verify_exit_code: int | None = None
    verdict: Literal["pass", "fail"] | None = None
    runtime_path: str = ""
    receipt: TestActivationReceipt | RunExperimentReceipt | None = None


def handle_runnable_operation(
    kind: RunnableKind,
    *,
    experiment_name: str = "",
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.record_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")

    try:
        ree = load_ree(layout, store)
        definition = _select_definition(ree, kind, experiment_name)
        runtime_path, runtime_digest = _check_preconditions(ree, definition, layout)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot {kind}: {exc}")
        return ActionResult.failed("precondition", f"cannot {kind}: {exc}")
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load {kind} inputs: {exc}")

    before_revision = revision_of(ree)
    runnable = _as_runnable(definition)
    label = definition.name if isinstance(definition, ExperimentDefinition) else "activation"
    timer = OperationTimer.start()
    outcome = run_runnable(
        workspace=layout.workspace.resolve(),
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = _outputs(outcome, runtime_path)
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
    expected_verify = definition.verify_script_path is not None
    if outcome.run_outputs.exit_code != 0 or (outcome.run_outputs.verify_exit_code == 0) != expected_verify:
        message = f"{kind} reported success without complete successful script outcomes"
        log("system", "error", message)
        return ActionResult.failed("internal", message)

    produced_output_digest: Digest | None = None
    if isinstance(definition, ExperimentDefinition) and definition.output_paths:
        try:
            produced_output_digest = _capture_experiment_outputs(layout, definition, log)
        except Exception as exc:
            return failed_from_exception(exc, f"failed to capture experiment outputs: {exc}")

    timing = timer.finish()
    receipt = _successful_receipt(
        definition,
        run_id=run_id,
        timing=timing,
        snapshot_digest=_source_snapshot(ree),
        runtime_path=runtime_path,
        runtime_digest=runtime_digest,
        produced_output_digest=produced_output_digest,
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


def _select_definition(ree: Ree, kind: RunnableKind, experiment_name: str) -> RunnableDefinition:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot run author operations")
    if kind == "test_activation":
        definition = ree.subject.definition.test_activation
        if definition is None:
            raise ReePreconditionError("no activation test is defined")
        return definition
    for experiment in ree.subject.definition.experiments:
        if experiment.name == experiment_name:
            return experiment
    raise ReePreconditionError(f"experiment {experiment_name!r} is not defined")


def _check_preconditions(
    ree: Ree,
    definition: RunnableDefinition,
    layout: ReeLayout,
) -> tuple[WorkspacePath | None, Digest | None]:
    if ree.subject.receipts.source is None:
        raise ReePreconditionError("source has not been acquired")
    _check_script(
        layout.workspace / str(definition.run_script_path),
        definition.run_script_digest,
        definition.run_script_size,
        label="run script",
    )
    if definition.verify_script_path is not None:
        if definition.verify_script_digest is None or definition.verify_script_size is None:
            raise AssertionError("definition admitted incomplete verification script identity")
        _check_script(
            layout.workspace / str(definition.verify_script_path),
            definition.verify_script_digest,
            definition.verify_script_size,
            label="verification script",
        )

    runtime = ree.subject.definition.runtime
    if runtime is None:
        return None, None
    build = ree.subject.receipts.build
    if build is None:
        raise ReePreconditionError("runtime has not been built")
    runtime_assessment = assess(ree).runtime
    if runtime_assessment.evidence != "current":
        detail = "; ".join(runtime_assessment.reasons) or "build evidence is not current"
        raise ReePreconditionError(detail)
    runtime_file = layout.workspace / str(runtime.runtime_path)
    if not runtime_file.is_file():
        raise ReePreconditionError(f"runtime artifact is missing: {runtime.runtime_path}")
    runtime_digest = digest_file(runtime_file)
    if runtime_digest != build.produced_runtime_digest:
        raise ReePreconditionError("runtime artifact does not match the selected build receipt")
    return runtime.runtime_path, runtime_digest


def _check_script(path: Path, expected_digest: Digest, expected_size: int, *, label: str) -> None:
    if not path.is_file():
        raise ReePreconditionError(f"the {label} is missing")
    if digest_file(path) != expected_digest or path.stat().st_size != expected_size:
        raise ReePreconditionError(f"the {label} does not match its definition")


def _as_runnable(definition: RunnableDefinition) -> RunnableSpec:
    return RunnableSpec(
        run_script=str(definition.run_script_path),
        verify_script=str(definition.verify_script_path or ""),
        output_paths=(
            tuple(str(path) for path in definition.output_paths) if isinstance(definition, ExperimentDefinition) else ()
        ),
    )


def _outputs(outcome: ExperimentRunOutcome, runtime_path: WorkspacePath | None) -> RunnableOperationOutputs:
    return RunnableOperationOutputs(
        **outcome.run_outputs.model_dump(),
        runtime_path=str(runtime_path or ""),
    )


def _source_snapshot(ree: Ree) -> Digest:
    source = ree.subject.receipts.source
    if source is None:
        raise AssertionError("runnable preconditions admitted a REE without source evidence")
    return source.snapshot_digest


def _successful_receipt(
    definition: RunnableDefinition,
    *,
    run_id: str,
    timing: OperationTiming,
    snapshot_digest: Digest,
    runtime_path: WorkspacePath | None,
    runtime_digest: Digest | None,
    produced_output_digest: Digest | None,
) -> TestActivationReceipt | RunExperimentReceipt:
    envelope = receipt_envelope(run_id, timing)
    if isinstance(definition, TestActivationDefinition):
        return TestActivationReceipt(
            **envelope,
            snapshot_digest=snapshot_digest,
            runtime_path=runtime_path,
            runtime_digest=runtime_digest,
            run_script_digest=definition.run_script_digest,
            verify_script_digest=definition.verify_script_digest,
            run_exit_code=0,
            verify_exit_code=0 if definition.verify_script_path is not None else None,
        )
    return RunExperimentReceipt(
        **envelope,
        experiment_name=definition.name,
        snapshot_digest=snapshot_digest,
        runtime_digest=runtime_digest,
        run_script_digest=definition.run_script_digest,
        verify_script_digest=definition.verify_script_digest,
        run_exit_code=0,
        verify_exit_code=0 if definition.verify_script_path is not None else None,
        produced_output_digest=produced_output_digest,
    )


def _capture_experiment_outputs(
    layout: ReeLayout,
    definition: ExperimentDefinition,
    log: LogSink,
) -> Digest:
    output_paths = [str(path) for path in definition.output_paths]
    result_store = layout.results_dir(definition.name)
    if result_store.exists():
        shutil.rmtree(result_store)
    for relative in output_paths:
        source = layout.workspace / relative
        if source.is_dir():
            shutil.copytree(source, result_store / relative, dirs_exist_ok=True)
        elif source.is_file():
            destination = result_store / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        else:
            log("system", "warn", f"declared output not found, skipping capture: {relative}")
    digest = digest_output_paths(layout.workspace, output_paths)
    if digest is None:
        raise AssertionError("declared experiment outputs produced no digest")
    return digest
