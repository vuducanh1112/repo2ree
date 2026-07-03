"""Handler for the activation operation.

Activation is the REE's required singleton probe: it proves the built runtime
is inhabitable by running its own run script. It runs through the same runner as
experiments — activation and experiments cannot drift because they share it.
"""

from __future__ import annotations

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.envelope.handlers._common import (
    patch_ree_intent,
    run_runnable_handler,
)
from repo2ree_core.experiment.experiment import ExpectedOutput, Runnable
from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.command import ActivationTestArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_activation_test(
    args: ActivationTestArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    def select(ree: ReeIntent, log: LogSink) -> tuple[Runnable, str] | None:
        activation = ree.activation
        if not activation.run_script.strip():
            log("system", "error", "Activation has no run script")
            return None
        return activation, "activation"

    def persist(store: ReeStore, ree: ReeIntent, snapshot: list[ExpectedOutput]) -> None:
        updated = ree.activation.model_copy(update={"outputs": snapshot})
        patch_ree_intent(store, {"activation": updated.model_dump()})

    return run_runnable_handler(
        operation="activation",
        mode=args.mode,
        select=select,
        persist=persist,
        snapshot_target="the activation",
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
