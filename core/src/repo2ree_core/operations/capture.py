"""Record commands and selected state boundaries independently of telemetry.

All dispatched commands cooperate on the author REE lock. Review snapshots
live in their own attempt directories; external writers are not synchronized.
A pending record means completion is unresolved, not that execution rolled back.
A canceled attempt is rolled back, to its before-snapshot, before it is captured;
an attempt whose capture failed is rolled back to it too, so that what the author
is told failed leaves nothing behind.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack, suppress

from repo2ree_core.bundle.repository_files import prepare_reproducer
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.persistence.capture_policy import write_capture_controls
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError, open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import next_operation_sequence, read_operation_history
from repo2ree_protocol.command import (
    Command,
    ReviewAcquireSourceCommand,
    ReviewActivationTestCommand,
    ReviewBuildRuntimeCommand,
    ReviewRunExperimentCommand,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.history import CompletedOperation, OperationRecord
from repo2ree_protocol.result import ActionResult, HistoryReference
from repo2ree_ree.digest import digest_bytes


def capture_command(
    *,
    layout: ReeLayout,
    cmd: Command,
    run_id: str,
    context: ExecutionContext,
    log: LogSink,
    execute: Callable[[], ActionResult],
) -> ActionResult:
    """Capture input, outcome and state; only a canceled attempt is rolled back.

    A cancel ends the attempt without its effects: the selected REE files go back to the
    before-snapshot, so its capture commit changes nothing. Any other outcome keeps, and
    commits, whatever the handler changed.
    """
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
        attempt_id=context.attempt_id,
        context=context,
        run_id=run_id,
        command=cmd.model_dump(mode="json"),
        scope=scope.root.relative_to(layout.root).as_posix(),
        phases=["pending"],
    )
    record_path = scope.git_dir / "repo2ree" / "operations" / f"{record.attempt_id}.json"
    result: ActionResult | None = None
    try:
        with ExitStack() as stack:
            history = stack.enter_context(open_history(layout))
            if any(item.attempt_id == context.attempt_id for item in read_operation_history(layout).operations):
                return ActionResult.failed("conflict", "Execution attempt already exists; retry with a new attempt ID")
            record.sequence = next_operation_sequence(layout)
            if scope != layout:
                author = ReeDirectory(layout).read_ree()
                record.author_seal_digest = str(author.seal.ree_digest) if author.seal else None
                history = stack.enter_context(open_history(scope))
            # This is outside the snapshot tree and is updated atomically.
            write_json_atomic(record_path, record.model_dump(mode="json"))
            history.capture_initial(existing=True)
            before = history.capture(operation="observe_existing_ree", reuse_unchanged=True)
            record.before_snapshot_id = before
            if scope == layout:
                record.step_evidence_before = step_evidence(layout, log)
            record.operation_status = "unknown"
            record.phases.append("executing")
            try:
                write_json_atomic(record_path, record.model_dump(mode="json"))
                try:
                    result = execute().model_copy(update={"context": context, "history": None})
                except Exception as exc:  # noqa: BLE001 — capture partial state from escaped handlers
                    log("system", "error", f"{cmd.operation} raised: {exc}")
                    result = failed_from_exception(exc, f"{cmd.operation} raised: {exc}")
                    result = result.model_copy(update={"context": context})
                record.operation_status = result.status
                record.operation_failure = result.failure
                record.result = result
                record.phases.append("completed")
                # Preserve the handler outcome even if snapshot publication fails.
                write_json_atomic(record_path, record.model_dump(mode="json"))
                if result.status == "canceled":
                    history.restore(before)
                if scope.manifest.is_file():
                    current = ReeDirectory(scope).read_ree()
                    if current.seal is None:
                        prepare_reproducer(scope, current)
                        write_capture_controls(scope, current)
                if scope == layout:
                    record.step_evidence_after = step_evidence(layout, log)
                record.after_snapshot_id, record.changed = history.commit_operation(
                    operation=cmd.operation,
                    record=CompletedOperation.model_validate(
                        {**record.model_dump(), "capture_status": "captured", "phases": [*record.phases, "captured"]}
                    ).model_dump(mode="json", exclude={"after_snapshot_id"}),
                )
            except (HistoryCaptureError, OSError, ValueError) as exc:
                # Still under the REE lock: put back what the attempt changed, since it is not recorded.
                rolled_back = _roll_back(history, before, log)
                raise _CaptureFailedError(str(exc), rolled_back=rolled_back) from exc
            record.capture_status = "captured"
            record.phases.append("captured")
            # The commit is authoritative. Cleanup is best-effort; a stale
            # pending record is reconciled with the published attempt on read.
            with suppress(OSError):
                record_path.unlink(missing_ok=True)
    except (_CaptureFailedError, HistoryCaptureError, OSError, ValueError) as exc:
        record_digest: str | None = None
        if not isinstance(exc, _CaptureFailedError):
            outcome = "nothing ran"  # The before-snapshot was never taken.
        elif exc.rolled_back:
            outcome = "the REE files were rolled back to how the attempt found them"
        else:
            outcome = "the REE files could not be rolled back"
        record.capture_status = "failed"
        record.capture_error = f"{exc}; {outcome}"
        record.phases.append("capture_failed")
        try:
            # The unique attempt path is safe to finalize after releasing locks.
            # If storage is unavailable, the last pending record remains evidence.
            if record_path.parent.is_dir():
                write_json_atomic(record_path, record.model_dump(mode="json"))
                # The record as written is what the result cites in place of a commit.
                record_digest = digest_bytes(record_path.read_bytes())
        except OSError as record_error:
            log("system", "error", f"Cannot finalize history record: {record_error}")
        message = f"REE history capture failed: {record.capture_error}"
        log("system", "error", message)
        failed = ActionResult.failed(
            "internal",
            message,
            details={"code": "history_capture_failed"},
            outputs=result.outputs if result is not None else {},
        )
        history_reference = _references(record).model_copy(update={"record_digest": record_digest})
        return failed.model_copy(update={"context": context, "history": history_reference})
    return result.model_copy(update={"history": _references(record)})


class _CaptureFailedError(Exception):
    """Publishing an attempt failed after its before-snapshot; whether its changes were undone."""

    def __init__(self, message: str, *, rolled_back: bool) -> None:
        super().__init__(message)
        self.rolled_back = rolled_back


def _roll_back(history: GitHistory, snapshot: str, log: LogSink) -> bool:
    """Restore the before-snapshot of an attempt whose capture failed; whether that worked."""
    try:
        history.restore(snapshot)
    except (HistoryCaptureError, OSError, ValueError) as exc:
        log("system", "error", f"Cannot roll the REE back after a failed capture: {exc}")
        return False
    return True


def step_evidence(layout: ReeLayout, log: LogSink) -> dict[str, str] | None:
    """Each author step's evidence standing; recording it must never fail the capture."""
    if not layout.manifest.is_file():
        return None
    try:
        report = audit(ReeDirectory(layout).read_ree())
    except Exception as exc:  # noqa: BLE001 — evidence about the REE, not a precondition of the command
        log("system", "warn", f"Step evidence was not recorded: {exc}")
        return None
    standing = {
        name: step.evidence
        for name in ("source", "evaluation", "hardware", "runtime", "sbom", "sbom_cross_check", "test_activation")
        if (step := getattr(report, name)) is not None
    }
    standing.update({f"experiment:{item.name}": item.run.evidence for item in report.experiments})
    return standing


def _references(record: OperationRecord) -> HistoryReference:
    return HistoryReference.model_validate(
        {
            "schema_version": record.schema_version,
            "selection_version": record.selection_version,
            "attempt_id": record.attempt_id,
            "scope": record.scope,
            "capture_status": record.capture_status,
            "before_snapshot_id": record.before_snapshot_id,
            "after_snapshot_id": record.after_snapshot_id,
            "operation_status": record.operation_status,
            "operation_failure": record.operation_failure.model_dump(mode="json") if record.operation_failure else None,
            "changed": record.changed if record.capture_status == "captured" else None,
        }
    )
