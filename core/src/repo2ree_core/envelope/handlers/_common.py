from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from repo2ree_core.container.run_script import CancelCheck, LogSink, run_workspace_script
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.experiment.experiment import ExpectedOutput, Runnable
from repo2ree_core.experiment.run import run_runnable
from repo2ree_core.path_safety import resolve_within
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.result import ActionResult

WORKSPACE_CONTROL_PREFIXES = (".workspace", ".upload.")


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

    if outcome.snapshot_to_persist is not None:
        try:
            persist(store, ree, outcome.snapshot_to_persist)
            outputs["snapshotApplied"] = True
            outputs["snapshotMessage"] = f"Saved {len(outcome.snapshot_to_persist)} baseline(s) to {snapshot_target}."
        except Exception as exc:
            log("system", "error", f"failed to persist snapshot: {exc}")
            outputs["snapshotApplied"] = False
            outputs["snapshotMessage"] = "Snapshot was not saved."
            return ActionResult(status="failed", exit_code=1, outputs=outputs)

    return ActionResult(status=outcome.status, exit_code=0, outputs=outputs)


def patch_ree_intent(store: ReeStore, patch: dict[str, Any]) -> None:
    if not store.metadata_exists():
        raise FileNotFoundError("metadata not found")
    intent = store.read_intent().apply_patch(patch)
    store.write_intent(intent)
