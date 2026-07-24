from __future__ import annotations

import shutil
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_bytes, digest_file_if_exists, digest_output_paths
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.experiment.experiment import Runnable
from repo2ree_core.experiment.run import RunnableRunOutputs, run_runnable
from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES, resolve_within
from repo2ree_core.receipts import (
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    RunExperimentReceipt,
    WorkspaceDrift,
    check_workspace_drift,
    declared_output_paths,
    receipt_run_id,
    record_receipt,
)
from repo2ree_core.run_script import CancelCheck, run_workspace_script
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus
from repo2ree_protocol.tracing import ReceiptInputAttrs


def resolve_workspace_path(layout: ReeLayout, rel_path: str) -> Path:
    path = rel_path.strip()
    candidate = resolve_within(layout.workspace, path)
    if candidate is None:
        raise ValueError("Invalid workspace path")
    # Only the leaf segment is guarded: the reserved control prefixes name files
    # (".workspace*", ".upload.*"), never directories, so a parent segment can
    # never collide with them.
    if PurePosixPath(path).name.startswith(WORKSPACE_CONTROL_PREFIXES):
        raise ValueError("Invalid workspace path")
    return candidate


@dataclass(frozen=True)
class _StepInputs:
    """The input slice of a workspace-dependent step, collected *before* the
    run so outputs landing in the workspace cannot leak into it."""

    snapshot_digest: str | None
    script_digest: str | None
    verify_script_digest: str | None
    runtime_path: str | None
    declared_runtime_digest: str | None
    workspace_drift: WorkspaceDrift


METADATA_MISSING = "metadata not found — was init-ree run?"


def open_ree_store(log: LogSink) -> tuple[ReeLayout, ReeStore] | ActionResult:
    """Open the workbench REE store, or the failure to return when it is absent.

    Every handler that touches REE state starts this way, so the guard and the
    message an author sees for "no REE here yet" live in one place. Callers
    ``return`` the ActionResult unchanged::

        opened = open_ree_store(log)
        if isinstance(opened, ActionResult):
            return opened
        layout, store = opened
    """
    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)
    if not store.metadata_exists():
        log("system", "error", METADATA_MISSING)
        return ActionResult.failed("precondition", METADATA_MISSING)
    return layout, store


def read_intent_or_none(store: ReeStore) -> ReeIntent | None:
    """The intent, or None when there is no readable metadata.

    For the read-only paths that must still answer when a REE is half-built
    (inference, step inputs) rather than fail the command.
    """
    with suppress(Exception):
        if store.metadata_exists():
            return store.read_intent()
    return None


def _collect_step_inputs(
    layout: ReeLayout,
    store: ReeStore,
    intent: ReeIntent | None,
    script_path: str,
    verify_script_path: str = "",
) -> _StepInputs:
    """Digest the step's inputs as they are at run start.

    The digests mirror the *materialization inputs* a re-runner will have —
    snapshot digest from the session, script content, the declared runtime
    artifact's state — never a digest of the live workspace tree.
    """
    snapshot_digest: str | None = None
    with suppress(Exception):
        if store.metadata_exists():
            snapshot_digest = store.read_session().source_snapshot_digest
    runtime_path = intent.runtime if intent else None
    return _StepInputs(
        snapshot_digest=snapshot_digest,
        script_digest=digest_file_if_exists(layout.workspace / script_path),
        verify_script_digest=(
            digest_file_if_exists(layout.workspace / verify_script_path) if verify_script_path else None
        ),
        runtime_path=runtime_path,
        declared_runtime_digest=(digest_file_if_exists(layout.workspace / runtime_path) if runtime_path else None),
        workspace_drift=check_workspace_drift(
            layout,
            excluded_paths=declared_output_paths(intent) if intent else set(),
        ),
    )


def _record_step_inputs(inputs: _StepInputs) -> None:
    """Surface the input slice on the command span as soon as it is known."""
    ReceiptInputAttrs(
        snapshot_digest=inputs.snapshot_digest,
        script_digest=inputs.script_digest,
        verify_script_digest=inputs.verify_script_digest,
        runtime_path=inputs.runtime_path,
        declared_runtime_digest=inputs.declared_runtime_digest,
        drift_status=inputs.workspace_drift.status,
        drift_changed_path_count=inputs.workspace_drift.changed_path_count,
    ).apply_current()


class BuildRuntimeOutputs(BaseModel):
    """Outputs of the bare build step (the bare runner's only client)."""

    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str
    container_exit_code: int | None = None
    receipt: dict[str, Any] | None = None


class RunnableStepOutputs(RunnableRunOutputs):
    """A runnable run's outputs plus the handler-level facts."""

    runtime_path: str = ""
    receipt: dict[str, Any] | None = None


class VersionConflictOutputs(BaseModel):
    """Outputs reported when an optimistic-concurrency etag check fails."""

    model_config = ConfigDict(extra="forbid")

    error_code: Literal["version_conflict"] = "version_conflict"
    path: str
    expected_version: str
    actual_version: str | None


def _result_from_run_outcome(
    status: ActionStatus,
    *,
    exit_code: int | None,
    outputs: dict[str, Any],
    operation: str,
) -> ActionResult:
    """Terminal ActionResult for a script-backed handler.

    A ``failed`` outcome carries an ``execution`` :class:`Failure` and the real
    underlying exit code (never a misleading 0), so a client learns *that* and
    *why* the author's script failed from the result itself, not the log tail.
    """
    if status == "failed":
        return ActionResult.failed(
            "execution",
            f"{operation} failed",
            exit_code=exit_code or 1,
            outputs=outputs,
        )
    return ActionResult(status=status, exit_code=0, outputs=outputs)


def run_bare_script_handler(
    script_path: str,
    *,
    operation: str,
    noun: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    """Run a single workspace script directly inside the workbench, unevaluated.

    The "bare" counterpart to :func:`run_runnable_handler`: it runs one script
    and reports its exit status, with no declared outputs to capture or evaluate.
    Used by the build_runtime handler. ``noun`` is the capitalised run name
    (e.g. "Build") used in log lines.
    """
    if is_canceled():
        log("system", "warn", f"{operation} canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    script_path = script_path.strip()
    try:
        resolve_workspace_path(layout, script_path)
    except Exception as exc:
        log("system", "error", f"invalid {noun.lower()} script path: {exc}")
        return ActionResult.failed("validation", f"invalid {noun.lower()} script path: {exc}")

    timer = OperationTimer.start()
    store = ReeStore(layout)
    intent = read_intent_or_none(store)
    inputs = _collect_step_inputs(layout, store, intent, script_path)
    _record_step_inputs(inputs)

    log("system", "info", f"Starting {noun.lower()} run {run_id}")
    log("system", "info", f"{noun} script: {script_path}")
    outcome = run_workspace_script(
        layout.workspace.resolve(),
        script_path,
        log=log,
        is_canceled=is_canceled,
    )

    outputs = BuildRuntimeOutputs(
        build_runtime_script_path=script_path,
        container_exit_code=outcome.exit_code,
    )

    # The bare runner currently serves only the build step; grow this into a
    # per-operation dispatch if other bare steps ever appear.
    if operation == "build_runtime":
        produced_runtime_digest = (
            digest_file_if_exists(layout.workspace / inputs.runtime_path)
            if outcome.status == "succeeded" and inputs.runtime_path
            else None
        )
        timing = timer.finish()
        receipt = BuildRuntimeReceipt(
            run_id=receipt_run_id(run_id),
            started_at=timing.started_at,
            finished_at=timing.finished_at,
            duration_ms=timing.duration_ms,
            recorded_at=timing.finished_at,
            status=outcome.status,
            workspace_drift=inputs.workspace_drift,
            snapshot_digest=inputs.snapshot_digest,
            build_script_path=script_path,
            build_script_digest=inputs.script_digest,
            runtime_path=inputs.runtime_path,
            produced_runtime_digest=produced_runtime_digest,
        )
        record_receipt(layout, receipt, log=log)
        outputs.receipt = receipt.model_dump()
        level = "info" if outcome.status == "succeeded" else "warn" if outcome.status == "canceled" else "error"
        log(
            "system",
            level,
            f"{noun} run {outcome.status} (exit code {outcome.exit_code}) in "
            f"{format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )

    return _result_from_run_outcome(
        outcome.status,
        exit_code=outcome.exit_code,
        outputs=outputs.model_dump(exclude_none=True),
        operation=operation,
    )


def _capture_experiment_outputs(
    layout: ReeLayout,
    name: str,
    output_paths: list[str],
    log: LogSink,
) -> str | None:
    """Copy an experiment's declared outputs into its produced-results store.

    Always runs after a successful experiment run (independent of sealing): the
    store (``results/<name>/``) is the author-side baseline a reviewer later
    diffs against, and the returned digest binds that baseline into the receipt.
    Returns ``None`` when the experiment declares no outputs. Copies each
    declared path preserving its relative structure so the store mirrors the
    workspace layout; the digest is computed over the live workspace (the source
    of truth), not the copied bytes.
    """
    if not output_paths:
        return None
    store = layout.results_dir(name)
    with suppress(Exception):
        if store.exists():
            shutil.rmtree(store)
    for rel in output_paths:
        source = resolve_workspace_path(layout, rel)
        if source.is_dir():
            shutil.copytree(source, store / rel, dirs_exist_ok=True)
        elif source.is_file():
            dest = store / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        else:
            log("system", "warn", f"declared output not found, skipping capture: {rel}")
    return digest_output_paths(layout.workspace, output_paths)


RunnableSelector = Callable[[ReeIntent, "LogSink"], tuple[Runnable, str] | None]


def run_runnable_handler(
    *,
    operation: str,
    select: RunnableSelector,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    """Run a selected :class:`Runnable` and record its receipt.

    Shared by the run_experiment and activation_test handlers, which differ
    only in *select* (which runnable to run, plus its label). *select* logs and
    returns ``None`` when the runnable can't be resolved.
    """
    if is_canceled():
        log("system", "warn", f"{operation} canceled before start")
        return ActionResult(status="canceled")

    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    try:
        ree = store.read_intent()
    except Exception as exc:
        log("system", "error", f"Invalid REE intent: {exc}")
        return ActionResult.failed("internal", f"Invalid REE intent: {exc}")

    selected = select(ree, log)
    if selected is None:
        # ``select`` has already logged why the runnable could not be resolved.
        return ActionResult.failed("precondition", f"{operation} target could not be resolved")
    runnable, label = selected

    timer = OperationTimer.start()
    inputs = _collect_step_inputs(layout, store, ree, runnable.run_script, runnable.verify_script)
    _record_step_inputs(inputs)

    outcome = run_runnable(
        workspace=layout.workspace.resolve(),
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = RunnableStepOutputs(
        **outcome.run_outputs.model_dump(),
        runtime_path=ree.runtime or "",
    )

    status: ActionStatus = outcome.status

    # Capture declared outputs after a successful experiment run (activation
    # produces no sealed result). Always copies to the produced-results store —
    # whether the store is packaged is an all-or-nothing seal-time choice
    # (`results_included`) handled at bundle time, not per-experiment state.
    produced_output_digest: str | None = None
    if operation == "run_experiment" and status == "succeeded" and runnable.output_paths:
        produced_output_digest = _capture_experiment_outputs(layout, label, runnable.output_paths, log)

    timing = timer.finish()
    receipt_cls = RunExperimentReceipt if operation == "run_experiment" else ActivationTestReceipt
    receipt: ActivationTestReceipt | RunExperimentReceipt = receipt_cls(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status=status,
        workspace_drift=inputs.workspace_drift,
        snapshot_digest=inputs.snapshot_digest,
        run_script_path=runnable.run_script,
        run_script_digest=inputs.script_digest,
        verify_script_path=runnable.verify_script,
        verify_script_digest=inputs.verify_script_digest,
        runtime_path=inputs.runtime_path,
        declared_runtime_digest=inputs.declared_runtime_digest,
    )
    if isinstance(receipt, RunExperimentReceipt):
        receipt.experiment_name = label
        receipt.produced_output_digest = produced_output_digest
    record_receipt(layout, receipt, log=log)
    outputs.receipt = receipt.model_dump()
    level = "info" if status == "succeeded" else "warn" if status == "canceled" else "error"
    log(
        "system",
        level,
        f"{operation} {status} in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )

    return _result_from_run_outcome(
        status,
        exit_code=outcome.run_outputs.verify_exit_code or outcome.run_outputs.exit_code,
        outputs=outputs.model_dump(exclude_none=True),
        operation=operation,
    )


def workspace_content_etag(store: ReeStore, path: str) -> str | None:
    """Current canonical etag of a workspace file, or None if it is absent.

    The API computes the etag it hands back after a write with the same
    ``digest_bytes``; the two are compared across a process boundary, so they
    must not be spelled independently.
    """
    if not store.workspace.is_file(path):
        return None
    return digest_bytes(store.workspace.read_bytes(path))


def check_expected_etag(store: ReeStore, path: str, expected: str, *, log: LogSink) -> ActionResult | None:
    """Verify an optimistic-concurrency etag; return the conflict result on mismatch.

    Runs inside the per-REE dispatch serialization, so a passed check cannot be
    invalidated before the mutation that follows it. Empty ``expected`` skips
    the check.
    """
    if not expected:
        return None
    actual = workspace_content_etag(store, path)
    if expected == actual:
        return None
    log("system", "error", f"etag mismatch for {path}: expected {expected}, actual {actual}")
    return ActionResult.failed(
        "conflict",
        f"etag mismatch for {path}: expected {expected}, actual {actual}",
        retryable=True,
        outputs=VersionConflictOutputs(
            path=path,
            expected_version=expected,
            actual_version=actual,
        ).model_dump(),
    )


def patch_ree_intent(store: ReeStore, patch: dict[str, Any]) -> None:
    if not store.metadata_exists():
        raise FileNotFoundError("metadata not found")
    intent = store.read_intent().apply_patch(patch)
    store.write_intent(intent)
