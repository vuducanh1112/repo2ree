"""Run the REE's activation alone, around a command that does nothing, against current evidence."""

from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers.author.runnable import handle_runnable_operation
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import ActivateExperimentEnvironmentArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult


def handle_activate_experiment_environment(
    args: ActivateExperimentEnvironmentArgs = ActivateExperimentEnvironmentArgs(),  # noqa: B008 — frozen by use: no handler changes its args
    *,
    layout: ReeLayout,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    return handle_runnable_operation(
        "activate_experiment_environment",
        again=args.again,
        layout=layout,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
