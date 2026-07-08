from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from repo2ree_core.digests import digest_file_if_exists, digest_json
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.experiment.experiment import ExpectedOutput, Runnable
from repo2ree_core.experiment.run import run_runnable
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
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult, ActionStatus


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
    runtime_path: str | None
    declared_runtime_digest: str | None
    workspace_drift: WorkspaceDrift


def _read_intent_or_none(store: ReeStore) -> ReeIntent | None:
    with suppress(Exception):
        if store.metadata_exists():
            return store.read_intent()
    return None


def _collect_step_inputs(
    layout: ReeLayout,
    store: ReeStore,
    intent: ReeIntent | None,
    script_path: str,
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
        runtime_path=runtime_path,
        declared_runtime_digest=(digest_file_if_exists(layout.workspace / runtime_path) if runtime_path else None),
        workspace_drift=check_workspace_drift(
            layout,
            excluded_paths=declared_output_paths(intent) if intent else set(),
        ),
    )


def run_bare_script_handler(
    script_path: str,
    *,
    operation: str,
    noun: str,
    output_key: str,
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
        return ActionResult(status="failed", exit_code=1)

    store = ReeStore(layout)
    intent = _read_intent_or_none(store)
    inputs = _collect_step_inputs(layout, store, intent, script_path)

    log("system", "info", f"Starting {noun.lower()} run {run_id}")
    log("system", "info", f"{noun} script: {script_path}")
    outcome = run_workspace_script(
        layout.workspace.resolve(),
        script_path,
        log=log,
        is_canceled=is_canceled,
    )

    log(
        "system",
        "info" if outcome.status == "succeeded" else "error",
        f"{noun} run {outcome.status} (exit code {outcome.exit_code})",
    )
    outputs: dict[str, Any] = {output_key: script_path}
    if outcome.exit_code is not None:
        outputs["containerExitCode"] = outcome.exit_code

    # The bare runner currently serves only the build step; grow this into a
    # per-operation dispatch if other bare steps ever appear.
    if operation == "build_runtime":
        receipt = BuildRuntimeReceipt(
            run_id=receipt_run_id(run_id),
            recorded_at=utc_now(),
            status=outcome.status,
            workspace_drift=inputs.workspace_drift,
            snapshot_digest=inputs.snapshot_digest,
            build_script_path=script_path,
            build_script_digest=inputs.script_digest,
            runtime_path=inputs.runtime_path,
            produced_runtime_digest=(
                digest_file_if_exists(layout.workspace / inputs.runtime_path)
                if outcome.status == "succeeded" and inputs.runtime_path
                else None
            ),
        )
        record_receipt(layout, receipt, log=log)
        outputs["receipt"] = receipt.model_dump(by_alias=True)

    return ActionResult(
        status=outcome.status,
        exit_code=outcome.exit_code if outcome.exit_code is not None else 0,
        outputs=outputs,
    )


RunnableSelector = Callable[[ReeIntent, "LogSink"], tuple[Runnable, str] | None]
SnapshotPersist = Callable[[ReeStore, ReeIntent, list[ExpectedOutput]], None]


def run_runnable_handler(
    *,
    operation: str,
    mode: Literal["verify", "snapshot"],
    select: RunnableSelector,
    persist: SnapshotPersist,
    snapshot_target: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    """Run a selected :class:`Runnable` and persist any captured snapshot.

    Shared by the run_experiment and activation_test handlers, which differ only
    in *select* (which runnable to run, plus its label) and *persist* (how the
    snapshot is written back into the intent). *select* logs and returns ``None``
    when the runnable can't be resolved; *snapshot_target* names the destination
    for the success message (e.g. "the intent", "the activation").
    """
    if is_canceled():
        log("system", "warn", f"{operation} canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)
    if not store.metadata_exists():
        log("system", "error", "metadata not found")
        return ActionResult(status="failed", exit_code=1)

    try:
        ree = store.read_intent()
    except Exception as exc:
        log("system", "error", f"Invalid REE intent: {exc}")
        return ActionResult(status="failed", exit_code=1)

    selected = select(ree, log)
    if selected is None:
        return ActionResult(status="failed", exit_code=1)
    runnable, label = selected

    inputs = _collect_step_inputs(layout, store, ree, runnable.run_script)
    # The spec the verdict will be relative to, digested before the run (a
    # snapshot-mode success rewrites it afterwards).
    expected_outputs_digest = digest_json([output.model_dump() for output in runnable.outputs])

    outcome = run_runnable(
        workspace=layout.workspace.resolve(),
        runnable=runnable,
        label=label,
        mode=mode,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = dict(outcome.run_outputs)
    outputs["runtimePath"] = ree.runtime or ""

    status: ActionStatus = outcome.status
    exit_code = 0
    if outcome.snapshot_to_persist is not None:
        try:
            persist(store, ree, outcome.snapshot_to_persist)
            outputs["snapshotApplied"] = True
            outputs["snapshotMessage"] = f"Saved {len(outcome.snapshot_to_persist)} baseline(s) to {snapshot_target}."
        except Exception as exc:
            log("system", "error", f"failed to persist snapshot: {exc}")
            outputs["snapshotApplied"] = False
            outputs["snapshotMessage"] = "Snapshot was not saved."
            status, exit_code = "failed", 1

    receipt_cls = RunExperimentReceipt if operation == "run_experiment" else ActivationTestReceipt
    receipt: ActivationTestReceipt | RunExperimentReceipt = receipt_cls(
        run_id=receipt_run_id(run_id),
        recorded_at=utc_now(),
        status=status,
        workspace_drift=inputs.workspace_drift,
        mode=mode,
        snapshot_digest=inputs.snapshot_digest,
        run_script_path=runnable.run_script,
        run_script_digest=inputs.script_digest,
        runtime_path=inputs.runtime_path,
        declared_runtime_digest=inputs.declared_runtime_digest,
    )
    if isinstance(receipt, RunExperimentReceipt):
        receipt.experiment_name = label
        receipt.expected_outputs_digest = expected_outputs_digest
    record_receipt(layout, receipt, log=log)
    outputs["receipt"] = receipt.model_dump(by_alias=True)

    return ActionResult(status=status, exit_code=exit_code, outputs=outputs)


def patch_ree_intent(store: ReeStore, patch: dict[str, Any]) -> None:
    if not store.metadata_exists():
        raise FileNotFoundError("metadata not found")
    intent = store.read_intent().apply_patch(patch)
    store.write_intent(intent)
