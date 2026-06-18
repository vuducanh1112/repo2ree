"""Handler for the activation operation.

Activation is the REE's required singleton probe: it proves the built runtime
is inhabitable by entering it through the same :class:`EnvEntry` every
experiment uses, and running the author's activation command (or a generic
liveness probe when none is declared). It runs through the *same* runner as
experiments — activation and experiments cannot drift because they share it.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.env_entry import DockerEntry
from repo2ree_core.envelope.handlers._common import (
    patch_ree_intent,
    resolve_workspace_path,
)
from repo2ree_core.experiment.run import run_runnable
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment import CancelCheck
from repo2ree_protocol.command import ActivationTestArgs
from repo2ree_protocol.result import ActionResult

# A blank activation still proves the runtime can be entered and a shell runs.
_DEFAULT_PROBE_COMMAND = 'echo "repo2ree activation: runtime entered"'


def handle_activation_test(
    args: ActivationTestArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "activation canceled before start")
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

    entry = ree.runtime_entry
    runtime_path = ree.runtime
    runtime_abs = None
    if isinstance(entry, DockerEntry):
        if not runtime_path:
            log("system", "error", "Runtime artifact is required before activation")
            return ActionResult(status="failed", exit_code=1)
        try:
            runtime_abs = resolve_workspace_path(layout, runtime_path)
        except Exception as exc:
            log("system", "error", f"invalid runtime path: {exc}")
            return ActionResult(status="failed", exit_code=1)
        if not runtime_abs.is_file():
            log("system", "error", f"Runtime artifact not found: {runtime_path}")
            return ActionResult(status="failed", exit_code=1)

    # Run a copy with a defaulted command so a blank activation is still a probe;
    # the stored activation (and its declared outputs) is otherwise untouched.
    activation = ree.activation
    if not activation.command.strip():
        log("system", "info", "No activation command declared — running generic liveness probe")
        activation = activation.model_copy(update={"command": _DEFAULT_PROBE_COMMAND})

    outcome = run_runnable(
        workspace=layout.workspace.resolve(),
        runnable=activation,
        label="activation",
        mode=args.mode,
        entry=entry,
        runtime_archive_path=runtime_abs,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = dict(outcome.run_outputs)
    outputs["runtimePath"] = runtime_path or ""

    if outcome.snapshot_to_persist is not None:
        updated = ree.activation.model_copy(update={"outputs": outcome.snapshot_to_persist})
        try:
            patch_ree_intent(store, {"activation": updated.model_dump()})
            outputs["snapshotApplied"] = True
            outputs["snapshotMessage"] = f"Saved {len(outcome.snapshot_to_persist)} baseline(s) to the activation."
        except Exception as exc:
            log("system", "error", f"failed to persist snapshot: {exc}")
            outputs["snapshotApplied"] = False
            outputs["snapshotMessage"] = "Snapshot was not saved."
            return ActionResult(status="failed", exit_code=1, outputs=outputs)

    return ActionResult(status=outcome.status, exit_code=0, outputs=outputs)
