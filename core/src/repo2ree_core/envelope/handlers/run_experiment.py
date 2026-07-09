from __future__ import annotations

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.envelope.handlers._common import run_runnable_handler
from repo2ree_core.experiment.experiment import Runnable
from repo2ree_core.run_script import CancelCheck
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

    return run_runnable_handler(
        operation="run_experiment",
        select=select,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
