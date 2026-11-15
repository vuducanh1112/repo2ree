from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.execution.runners import ScriptRunner
from repo2ree_core.operations.handlers.author.runnable import handle_runnable_operation
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import RunExperimentArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult


def handle_run_experiment(
    args: RunExperimentArgs,
    *,
    layout: ReeLayout,
    runner: ScriptRunner,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    return handle_runnable_operation(
        "run_experiment",
        experiment_name=args.experiment_name,
        layout=layout,
        runner=runner,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
