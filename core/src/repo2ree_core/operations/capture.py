"""Record commands and selected state boundaries independently of telemetry.

All dispatched commands cooperate on the author REE lock. Review snapshots
live in their own attempt directories; external writers are not synchronized.
A pending record means completion is unresolved, not that execution rolled back.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from typing import Any
from uuid import uuid4

from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import HistoryCaptureError, open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import OperationRecord, next_operation_sequence
from repo2ree_protocol.command import (
    Command,
    ReviewAcquireSourceCommand,
    ReviewActivationTestCommand,
    ReviewBuildRuntimeCommand,
    ReviewRunExperimentCommand,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def capture_command(
    *, layout: ReeLayout, cmd: Command, run_id: str, log: LogSink, execute: Callable[[], ActionResult]
) -> ActionResult:
    """Capture input, outcome and state without implying transactional rollback."""
    # Preserve missing-REE preconditions without creating a new REE implicitly.
    if not layout.manifest.is_file():
        return execute()
    scope = layout
    if isinstance(
        cmd,
        (
            ReviewAcquireSourceCommand,
            ReviewBuildRuntimeCommand,
            ReviewActivationTestCommand,
            ReviewRunExperimentCommand,
        ),
    ):
        scope = layout.review(cmd.args.review_id)
    record = OperationRecord(
        attempt_id=uuid4().hex,
        run_id=run_id,
        command=cmd.model_dump(mode="json"),
        scope=scope.root.relative_to(layout.root).as_posix(),
    )
    record_path = scope.git_dir / "repo2ree" / "operations" / f"{record.attempt_id}.json"
    result: ActionResult | None = None
    try:
        with ExitStack() as stack:
            history = stack.enter_context(open_history(layout))
            record.sequence = next_operation_sequence(layout)
            if scope != layout:
                author = ReeDirectory(layout).read_ree()
                record.author_seal_digest = str(author.seal.ree_digest) if author.seal else None
                history = stack.enter_context(open_history(scope))
            # This is outside the snapshot tree and is updated atomically.
            write_json_atomic(record_path, record.model_dump(mode="json"))
            history.capture_initial(existing=True)
            record.before_snapshot_id = history.capture(operation="observe_existing_ree", reuse_unchanged=True)
            record.operation_status = "unknown"
            write_json_atomic(record_path, record.model_dump(mode="json"))
            try:
                result = execute()
            except Exception as exc:  # noqa: BLE001 — capture partial state from escaped handlers
                log("system", "error", f"{cmd.operation} raised: {exc}")
                result = failed_from_exception(exc, f"{cmd.operation} raised: {exc}")
            record.operation_status = result.status
            record.operation_failure = result.failure
            # Preserve the handler outcome even if snapshot publication fails.
            write_json_atomic(record_path, record.model_dump(mode="json"))
            record.after_snapshot_id = history.capture(
                operation=cmd.operation,
                run_id=run_id,
                outcome=result.status,
                attempt_id=record.attempt_id,
                reuse_unchanged=True,
            )
            record.capture_status = "captured"
            write_json_atomic(record_path, record.model_dump(mode="json"))
    except (HistoryCaptureError, OSError, ValueError) as exc:
        record.capture_status = "failed"
        record.capture_error = str(exc)
        try:
            # The unique attempt path is safe to finalize after releasing locks.
            # If storage is unavailable, the last pending record remains evidence.
            if record_path.parent.is_dir():
                write_json_atomic(record_path, record.model_dump(mode="json"))
        except OSError as record_error:
            log("system", "error", f"Cannot finalize history record: {record_error}")
        message = f"REE history capture failed: {exc}; REE files have not been rolled back"
        log("system", "error", message)
        return ActionResult.failed(
            "internal",
            message,
            details={"code": "history_capture_failed"},
            outputs={**(result.outputs if result is not None else {}), "history": _references(record)},
        )
    return result.model_copy(update={"outputs": {**result.outputs, "history": _references(record)}})


def _references(record: OperationRecord) -> dict[str, Any]:
    return {
        "schema_version": record.schema_version,
        "selection_version": record.selection_version,
        "attempt_id": record.attempt_id,
        "scope": record.scope,
        "capture_status": record.capture_status,
        "before_snapshot_id": record.before_snapshot_id,
        "after_snapshot_id": record.after_snapshot_id,
        "operation_status": record.operation_status,
        "operation_failure": record.operation_failure.model_dump(mode="json") if record.operation_failure else None,
        "changed": (record.before_snapshot_id != record.after_snapshot_id)
        if record.capture_status == "captured"
        else None,
    }
