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

from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt, receipt_envelope
from repo2ree_core.evidence.receipts.store import record_receipt
from repo2ree_core.execution.process import CancelCheck, run_workspace_script
from repo2ree_core.operations.handlers.step_runner import (
    collect_step_inputs,
    outcome_log_level,
    read_intent_or_none,
    record_step_inputs,
    resolve_workspace_path,
    result_from_run_outcome,
)
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult

_OPERATION = "build_runtime"


class BuildRuntimeOutputs(BaseModel):
    """Outputs of the build step."""

    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str
    container_exit_code: int | None = None
    receipt: dict[str, Any] | None = None


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
    store = ReeStore(layout)
    intent = read_intent_or_none(store, log=log)
    inputs = collect_step_inputs(layout, store, intent, RESERVED_BUILD_SCRIPT, log=log)
    record_step_inputs(inputs)

    log("system", "info", f"Starting build run {run_id}")
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
    timing = timer.finish()
    receipt = BuildRuntimeReceipt(
        **receipt_envelope(run_id, timing, outcome.status),
        workspace_drift=inputs.workspace_drift,
        snapshot_digest=inputs.snapshot_digest,
        build_script_path=RESERVED_BUILD_SCRIPT,
        build_script_digest=inputs.script_digest,
        runtime_path=inputs.runtime_path,
        produced_runtime_digest=produced_runtime_digest,
    )
    record_receipt(layout, receipt, log=log)
    log(
        "system",
        outcome_log_level(outcome.status),
        f"Build run {outcome.status} (exit code {outcome.exit_code}) in "
        f"{format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )

    outputs = BuildRuntimeOutputs(
        build_runtime_script_path=RESERVED_BUILD_SCRIPT,
        container_exit_code=outcome.exit_code,
        receipt=receipt.model_dump(),
    )
    return result_from_run_outcome(
        outcome.status,
        exit_code=outcome.exit_code,
        outputs=outputs.model_dump(exclude_none=True),
        operation=_OPERATION,
    )
