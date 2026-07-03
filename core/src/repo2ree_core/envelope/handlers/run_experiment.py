from __future__ import annotations

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.envelope.handlers._common import (
    patch_ree_intent,
    run_runnable_handler,
)
from repo2ree_core.experiment.experiment import ExpectedOutput, Runnable
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.command import RunExperimentArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_run_experiment(
    args: RunExperimentArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    def select(ree: ReeIntent, log: LogSink) -> tuple[Runnable, str] | None:
        experiment = next((exp for exp in ree.experiments if exp.name == args.experiment_name), None)
        if experiment is None:
            log("system", "error", f"Experiment {args.experiment_name!r} not found")
            return None
        if not experiment.run_script.strip():
            log("system", "error", "Experiment has no run script")
            return None
        return experiment, experiment.name

    def persist(store: ReeStore, ree: ReeIntent, snapshot: list[ExpectedOutput]) -> None:
        raw_experiments = [e.model_dump() for e in ree.experiments]
        for raw_exp in raw_experiments:
            if raw_exp.get("name") == args.experiment_name:
                raw_exp["outputs"] = [o.model_dump() for o in snapshot]
                break
        patch_ree_intent(store, {"experiments": raw_experiments})

    return run_runnable_handler(
        operation="run_experiment",
        mode=args.mode,
        select=select,
        persist=persist,
        snapshot_target="the intent",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
