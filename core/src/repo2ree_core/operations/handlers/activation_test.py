"""Handler for the activation operation.

Activation is the REE's required singleton probe: it proves the built runtime
is inhabitable by running its own run script. It runs through the same runner as
experiments — activation and experiments cannot drift because they share it.
"""

from __future__ import annotations

from repo2ree_core.domain.experiment import Runnable
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.evidence.receipts.models import ActivationTestReceipt
from repo2ree_core.execution.experiment.resolve import RunnableResolutionError, resolve_activation_runnable
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers.step_runner import RunnableStep, run_runnable_handler
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_activation_test(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    def select(ree: ReeIntent, log: LogSink) -> tuple[Runnable, str] | None:
        try:
            activation = resolve_activation_runnable(ree)
        except RunnableResolutionError as exc:
            log("system", "error", str(exc))
            return None
        return activation, "activation"

    return run_runnable_handler(
        RunnableStep(
            operation="activation",
            select=select,
            receipt_cls=ActivationTestReceipt,
            # Activation proves the runtime comes up; it produces no sealed
            # result, so there is no baseline to capture.
            captures_declared_outputs=False,
        ),
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
