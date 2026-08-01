"""Handler for the build_runtime operation.

The one step that runs a workspace script without a :class:`Runnable` around
it: the reserved build script fully defines how the runtime is produced, and
there is nothing to verify afterwards — no declared outputs to capture, no
verify script whose exit code is a verdict. What the step contributes is the
receipt binding the build's inputs to the artifact it left behind, which is
what a reviewer later rebuilds against.

That is why the run lives here rather than behind a shared runner: "run one
script and receipt it" is not a second general shape, it is this step.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_serializer

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.primitives import ScriptPath
from repo2ree_core.domain.ree.receipt import BuildRuntimeReceipt
from repo2ree_core.domain.ree.transitions import request_runtime_build
from repo2ree_core.execution.process import CancelCheck, run_workspace_script
from repo2ree_core.operations.steps.author import (
    collect_step_inputs,
    dump_receipt_whole,
    read_intent_or_none,
    record_step_inputs,
    resolve_workspace_path,
    result_from_run_outcome,
    settle_step,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import load_ree
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

_OPERATION = "build_runtime"


class BuildRuntimeOutputs(BaseModel):
    """Outputs of the build step."""

    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str
    container_exit_code: int | None = None
    receipt: BuildRuntimeReceipt | None = None

    _dump_receipt = field_serializer("receipt")(dump_receipt_whole)


def handle_build_runtime(
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    # The build script is fixed: always the reserved, REE-owned build script.
    layout = ReeLayout.in_workbench()
    try:
        resolve_workspace_path(layout, RESERVED_BUILD_SCRIPT)
    except ValueError as exc:
        log("system", "error", f"invalid build script path: {exc}")
        return ActionResult.failed("validation", f"invalid build script path: {exc}")

    timer = OperationTimer.start()
    store = ReeDirectory(layout)
    intent = read_intent_or_none(store, log=log)
    inputs = collect_step_inputs(layout, store, intent, RESERVED_BUILD_SCRIPT, log=log)
    record_step_inputs(inputs)

    try:
        transition = request_runtime_build(
            load_ree(layout, store),
            snapshot_digest=inputs.snapshot_digest,
            build_script_digest=inputs.script_digest,
        )
    except (OSError, ValueError) as exc:
        log("system", "error", f"cannot build runtime: {exc}")
        return ActionResult.failed("precondition", f"cannot build runtime: {exc}")

    log("system", "info", f"Starting build run {run_id}")
    log("system", "info", f"REE revision: {transition.revision}")
    log("system", "info", f"Build script: {RESERVED_BUILD_SCRIPT}")
    outcome = run_workspace_script(
        layout.workspace.resolve(),
        RESERVED_BUILD_SCRIPT,
        log=log,
        is_canceled=is_canceled,
    )

    # Only a successful build can have produced the declared runtime; digesting
    # after a failure would bind this receipt to whatever the last good build
    # left at that path.
    produced_runtime_digest = (
        digest_file_if_exists(layout.workspace / inputs.runtime_path)
        if outcome.status == "succeeded" and inputs.runtime_path
        else None
    )
    receipt = settle_step(
        layout,
        lambda envelope: BuildRuntimeReceipt(
            **envelope,
            workspace_drift=inputs.workspace_drift,
            snapshot_digest=inputs.snapshot_digest,
            build_script_path=ScriptPath(RESERVED_BUILD_SCRIPT),
            build_script_digest=inputs.script_digest,
            runtime_path=inputs.runtime_path,
            produced_runtime_digest=produced_runtime_digest,
        ),
        operation=_OPERATION,
        run_id=run_id,
        timer=timer,
        status=outcome.status,
        log=log,
        detail=f" (exit code {outcome.exit_code})",
    )

    outputs = BuildRuntimeOutputs(
        build_runtime_script_path=RESERVED_BUILD_SCRIPT,
        container_exit_code=outcome.exit_code,
        receipt=receipt,
    )
    return result_from_run_outcome(
        outcome.status,
        exit_code=outcome.exit_code,
        outputs=outputs.model_dump(exclude_none=True),
        operation=_OPERATION,
    )
