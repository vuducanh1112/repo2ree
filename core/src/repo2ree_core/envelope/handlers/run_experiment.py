from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree import REE
from repo2ree_protocol.command import RunExperimentArgs
from repo2ree_core.envelope.handlers._common import (
    patch_ree_draft_metadata,
    resolve_workspace_path,
)
from repo2ree_protocol.result import ActionResult
from repo2ree_core.experiment.run import run_experiment
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment import CancelCheck


def handle_run_experiment(
    args: RunExperimentArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "run_experiment canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)
    if not store.metadata_exists():
        log("system", "error", "metadata not found")
        return ActionResult(status="failed", exit_code=1)

    try:
        metadata = store.read_metadata_json()
        ree = REE.from_metadata(metadata)
    except Exception as exc:
        log("system", "error", f"Invalid REE draft: {exc}")
        return ActionResult(status="failed", exit_code=1)

    runtime_path = ree.runtime.strip()
    if not runtime_path:
        log(
            "system", "error", "Runtime artifact is required before running experiments"
        )
        return ActionResult(status="failed", exit_code=1)
    try:
        runtime_abs = resolve_workspace_path(layout, runtime_path)
    except Exception as exc:
        log("system", "error", f"invalid runtime path: {exc}")
        return ActionResult(status="failed", exit_code=1)
    if not runtime_abs.is_file():
        log("system", "error", f"Runtime artifact not found: {runtime_path}")
        return ActionResult(status="failed", exit_code=1)

    experiment = next(
        (exp for exp in ree.experiments if exp.name == args.experiment_name), None
    )
    if experiment is None:
        log("system", "error", f"Experiment {args.experiment_name!r} not found")
        return ActionResult(status="failed", exit_code=1)
    if not experiment.command.strip():
        log("system", "error", "Experiment has no command to run")
        return ActionResult(status="failed", exit_code=1)

    outcome = run_experiment(
        workspace=layout.workspace.resolve(),
        experiment=experiment,
        mode=args.mode,
        runtime_archive_path=runtime_abs,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = dict(outcome.run_outputs)
    outputs["runtimePath"] = runtime_path

    if outcome.snapshot_to_persist is not None:
        raw_experiments = list(
            (metadata.get("reeDraft") or {}).get("experiments") or []
        )
        updated = False
        for i, raw_exp in enumerate(raw_experiments):
            if raw_exp.get("name") == args.experiment_name:
                raw_experiments[i] = {
                    **raw_exp,
                    "outputs": [o.model_dump() for o in outcome.snapshot_to_persist],
                }
                updated = True
                break
        if updated:
            try:
                patch_ree_draft_metadata(store, {"experiments": raw_experiments})
                outputs["snapshotApplied"] = True
                outputs["snapshotMessage"] = (
                    f"Saved {len(outcome.snapshot_to_persist)} baseline(s) to the draft."
                )
            except Exception as exc:
                log("system", "error", f"failed to persist snapshot: {exc}")
                outputs["snapshotApplied"] = False
                outputs["snapshotMessage"] = "Snapshot was not saved."
                return ActionResult(status="failed", exit_code=1, outputs=outputs)

    return ActionResult(status=outcome.status, exit_code=0, outputs=outputs)
