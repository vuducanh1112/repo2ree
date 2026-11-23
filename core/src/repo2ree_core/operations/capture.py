from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack, suppress
from pathlib import Path

from repo2ree_core.bundle.repository_files import prepare_reproducer
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations import stage as staging
from repo2ree_core.persistence.capture_policy import write_capture_controls
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_json_atomic
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError, open_history
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.operation_history import next_operation_sequence, read_operation_history
from repo2ree_core.workspace.integrity import (
    drift_refusal,
    find_drift,
    lay_out_scripts,
    recordable_edits,
)
from repo2ree_protocol.command import (
    Command,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.history import CompletedOperation, OperationRecord
from repo2ree_protocol.result import ActionResult, DriftedFile, HistoryReference
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.layout import OVERLAY


def capture_command(
    *,
    layout: ReeLayout,
    cmd: Command,
    run_id: str,
    context: ExecutionContext,
    log: LogSink,
    execute: Callable[[ReeLayout], ActionResult],
    records_edit: str | None = None,
) -> ActionResult:
    if not layout.manifest.is_file():
        return execute(layout)
    scope = _scope(layout, cmd)
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
            write_json_atomic(record_path, record.model_dump(mode="json"))
            history.capture_initial(existing=True)
            record.drift_found = find_drift(layout)
            if records_edit is not None:
                record.drift_recorded = f"{OVERLAY}/{records_edit}"
            refusal = _refusal(layout, record.drift_found, records_edit, str(cmd.operation))
            if refusal is not None:
                return _refuse(layout, scope, history, record, record_path, cmd.operation, refusal, context, log)
            before = history.head_snapshot()
            if before is None:
                raise HistoryCaptureError("the REE has no history to begin the attempt on")
            edited = layout.overlay_file(records_edit).read_bytes() if records_edit is not None else None
            record.before_snapshot_id = before
            if scope == layout:
                record.step_evidence_before = step_evidence(layout, log)
            record.operation_status = "unknown"
            record.phases.append("executing")
            stage: staging.Stage | None = None
            unchanged = False
            try:
                if str(cmd.operation) not in _ON_THE_REE:
                    stage = staging.lay_out(layout, record.attempt_id)
                write_json_atomic(record_path, record.model_dump(mode="json"))
                try:
                    result = execute(stage.layout if stage is not None else layout)
                    result = result.model_copy(update={"context": context, "history": None})
                except Exception as exc:  # noqa: BLE001
                    log("system", "error", f"{cmd.operation} raised: {exc}")
                    result = failed_from_exception(exc, f"{cmd.operation} raised: {exc}")
                    result = result.model_copy(update={"context": context})
                record.operation_status = result.status
                record.operation_failure = result.failure
                record.result = result
                if stage is not None:
                    record.drift_after = _drift_beside(layout, record.drift_recorded, edited, log)
                record.phases.append("completed")
                write_json_atomic(record_path, record.model_dump(mode="json"))
                unchanged = result.status == "canceled" or (edited is not None and result.status != "succeeded")
                if stage is None:
                    if unchanged:
                        _restore(history, before)
                    _publish(layout, scope, history, record, cmd.operation, log)
                else:
                    if beyond := staging.changed_beyond(stage, record.scope):
                        raise HistoryCaptureError(
                            f"{cmd.operation} changed what it is not recorded in: {', '.join(beyond)}"
                        )
                    _publish(
                        stage.layout,
                        stage.scope(record.scope),
                        stage.history(record.scope),
                        record,
                        cmd.operation,
                        log,
                        unchanged=unchanged,
                    )
            except (HistoryCaptureError, OSError, ValueError) as exc:
                rolled_back = _roll_back(history, before, log) if stage is None else True
                if stage is not None:
                    staging.discard(stage)
                raise _CaptureFailedError(str(exc), rolled_back=rolled_back, staged=stage is not None) from exc
            record.capture_status = "captured"
            record.phases.append("captured")
            if stage is not None:
                if not unchanged and record.after_snapshot_id is not None:
                    try:
                        staging.put_back(stage, record.scope, before, record.after_snapshot_id)
                    except (HistoryCaptureError, OSError, ValueError) as exc:
                        log("system", "error", f"Cannot put the REE's files as the attempt left them: {exc}")
                staging.discard(stage)
            elif edited is not None and records_edit is not None and result.status != "succeeded":
                layout.overlay_file(records_edit).write_bytes(edited)
            with suppress(OSError):
                record_path.unlink(missing_ok=True)
    except (_CaptureFailedError, HistoryCaptureError, OSError, ValueError) as exc:
        record_digest: str | None = None
        if not isinstance(exc, _CaptureFailedError):
            outcome = "nothing ran"
        elif exc.staged:
            outcome = "the REE files were left as the attempt found them"
        elif exc.rolled_back:
            outcome = "the REE files were rolled back to how the attempt found them"
        else:
            outcome = "the REE files could not be rolled back"
        record.capture_status = "failed"
        record.capture_error = f"{exc}; {outcome}"
        record.phases.append("capture_failed")
        try:
            if record_path.parent.is_dir():
                write_json_atomic(record_path, record.model_dump(mode="json"))
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
        return failed.model_copy(update={"context": context, "history": _references(record, record_digest)})
    return result.model_copy(update={"history": _references(record)})


_ON_THE_REE = frozenset({"load_ree_bundle"})


def _drift_beside(layout: ReeLayout, recorded: str | None, edited: bytes | None, log: LogSink) -> list[DriftedFile]:
    try:
        drift = find_drift(layout)
    except (HistoryCaptureError, OSError, ValueError) as exc:
        log("system", "warn", f"Cannot check the REE once the handler returned: {exc}")
        return []
    if recorded is not None:
        with suppress(OSError):
            if edited is None or (layout.root / recorded).read_bytes() == edited:
                drift = [item for item in drift if item.path != recorded]
    if drift:
        log(
            "system",
            "warn",
            "changed beside this attempt while it ran, so not recorded: " + drift_refusal(layout, drift),
        )
    return drift


def _refusal(layout: ReeLayout, drift: list[DriftedFile], records_edit: str | None, operation: str) -> str | None:
    if not drift:
        return None
    edits = recordable_edits(layout, drift)
    if records_edit is not None and records_edit in edits:
        return None
    return drift_refusal(layout, drift)


def _refuse(
    layout: ReeLayout,
    scope: ReeLayout,
    history: GitHistory,
    record: OperationRecord,
    record_path: Path,
    operation: str,
    message: str,
    context: ExecutionContext,
    log: LogSink,
) -> ActionResult:
    log("system", "error", message)
    head = history.head_snapshot()
    if head is None:
        raise HistoryCaptureError("an REE with drift has no history to compare it with")
    result = ActionResult.failed("precondition", message, origin="core", details={"code": "drift"})
    result = result.model_copy(update={"context": context, "history": None})
    record.before_snapshot_id = head
    record.phases.append("executing")
    record.operation_status = result.status
    record.operation_failure = result.failure
    record.result = result
    record.phases.append("completed")
    record.capture_status = "failed"
    record.capture_error = "the REE changed outside ree, so the refusal is kept beside its history"
    record.phases.append("capture_failed")
    write_json_atomic(record_path, record.model_dump(mode="json"))
    return result.model_copy(update={"history": _references(record, _digest_of(record_path))})


def _publish(
    layout: ReeLayout,
    scope: ReeLayout,
    history: GitHistory,
    record: OperationRecord,
    operation: str,
    log: LogSink,
    *,
    unchanged: bool = False,
) -> None:
    if scope.manifest.is_file() and not unchanged:
        current = ReeDirectory(scope).read_ree()
        if current.seal is None:
            prepare_reproducer(scope, current)
            write_capture_controls(scope, current)
    if scope == layout:
        record.step_evidence_after = record.step_evidence_before if unchanged else step_evidence(layout, log)
    record.after_snapshot_id, record.changed = history.commit_operation(
        unchanged=unchanged,
        operation=operation,
        record=CompletedOperation.model_validate(
            {**record.model_dump(), "capture_status": "captured", "phases": [*record.phases, "captured"]}
        ).model_dump(mode="json", exclude={"after_snapshot_id"}),
    )


def settle_interrupted(
    *,
    layout: ReeLayout,
    attempt_id: str,
    log: LogSink,
    cmd: Command | None = None,
    run_id: str | None = None,
    context: ExecutionContext | None = None,
) -> ActionResult | None:
    record = next((item for item in read_operation_history(layout).operations if item.attempt_id == attempt_id), None)
    if record is None:
        if cmd is None or not layout.manifest.is_file():
            return None
        return _record_unbegun(layout, cmd, attempt_id, run_id, context, log)
    scope = layout if record.scope == "." else ReviewLayout(root=layout.root / record.scope)
    record_path = scope.git_dir / "repo2ree" / "operations" / f"{attempt_id}.json"
    if record.capture_status == "captured":
        return _settled_result(record)
    if record.capture_status == "failed":
        return _failed_capture(record, _digest_of(record_path), log)
    phase = record.phases[-1] if record.phases else "pending"
    staged = str(record.command.get("operation", "")) not in _ON_THE_REE
    with ExitStack() as stack:
        history = stack.enter_context(open_history(layout))
        if scope != layout:
            history = stack.enter_context(open_history(scope))
        staging.discard_left(layout, attempt_id)
        if phase == "pending" or record.before_snapshot_id is None:
            return _capture_failed(record, record_path, "the executor was lost before the attempt began", log)
        if phase == "completed":
            rolled_back = True if staged else _roll_back(history, record.before_snapshot_id, log)
            outcome = "rolled back" if rolled_back else "could not be rolled back"
            error = f"the executor was lost before the attempt was captured; the REE files {outcome}"
            return _capture_failed(record, record_path, error, log)
        message = "The executor ended without reporting; the REE was rolled back to how the attempt found it"
        failed = ActionResult.failed(
            "internal", message, origin="core", retryable=True, details={"code": "interrupted"}
        )
        result = failed.model_copy(update={"context": record.context})
        record.operation_status = "interrupted"
        record.operation_failure = result.failure
        record.result = result
        if staged:
            record.drift_after = _drift_beside(layout, record.drift_recorded, None, log)
        record.phases.append("completed")
        try:
            write_json_atomic(record_path, record.model_dump(mode="json"))
            if not staged:
                _restore(history, record.before_snapshot_id)
            _publish(layout, scope, history, record, str(record.command.get("operation", "")), log, unchanged=staged)
        except (HistoryCaptureError, OSError, ValueError) as exc:
            rolled_back = True if staged else _roll_back(history, record.before_snapshot_id, log)
            outcome = "rolled back" if rolled_back else "could not be rolled back"
            return _capture_failed(record, record_path, f"{exc}; the REE files {outcome}", log)
        record.capture_status = "captured"
        record.phases.append("captured")
        with suppress(OSError):
            record_path.unlink(missing_ok=True)
    log("system", "error", message)
    return result.model_copy(update={"history": _references(record)})


def _record_unbegun(
    layout: ReeLayout,
    cmd: Command,
    attempt_id: str,
    run_id: str | None,
    context: ExecutionContext | None,
    log: LogSink,
) -> ActionResult:
    scope = _scope(layout, cmd)
    context = (context or ExecutionContext.new()).model_copy(update={"attempt_id": attempt_id})
    record = OperationRecord(
        attempt_id=attempt_id,
        context=context,
        run_id=run_id or f"manual-{attempt_id}",
        command=cmd.model_dump(mode="json"),
        scope=scope.root.relative_to(layout.root).as_posix(),
        phases=["pending"],
    )
    record_path = scope.git_dir / "repo2ree" / "operations" / f"{attempt_id}.json"
    with open_history(layout):
        record.sequence = next_operation_sequence(layout)
        record_path.parent.mkdir(parents=True, exist_ok=True)
        return _capture_failed(record, record_path, "the executor was lost before the attempt began", log)


def _scope(layout: ReeLayout, cmd: Command) -> ReeLayout:
    review_id = getattr(cmd.args, "review_id", None)
    return layout.review(review_id) if review_id else layout


def _settled_result(record: OperationRecord) -> ActionResult:
    reported = record.result or ActionResult.failed(
        "internal", "The attempt was captured without a result", origin="core"
    )
    return reported.model_copy(update={"context": record.context, "history": _references(record)})


def _capture_failed(record: OperationRecord, record_path: Path, error: str, log: LogSink) -> ActionResult:
    record.capture_status = "failed"
    record.capture_error = error
    record.phases.append("capture_failed")
    digest: str | None = None
    try:
        write_json_atomic(record_path, record.model_dump(mode="json"))
        digest = _digest_of(record_path)
    except OSError as record_error:
        log("system", "error", f"Cannot finalize history record: {record_error}")
    return _failed_capture(record, digest, log)


def _failed_capture(record: OperationRecord, digest: str | None, log: LogSink) -> ActionResult:
    message = f"REE history capture failed: {record.capture_error}"
    log("system", "error", message)
    failed = ActionResult.failed("internal", message, details={"code": "history_capture_failed"})
    return failed.model_copy(update={"context": record.context, "history": _references(record, digest)})


def _digest_of(record_path: Path) -> str | None:
    try:
        return digest_bytes(record_path.read_bytes())
    except OSError:
        return None


class _CaptureFailedError(Exception):
    def __init__(self, message: str, *, rolled_back: bool, staged: bool = False) -> None:
        super().__init__(message)
        self.rolled_back = rolled_back
        self.staged = staged


def _restore(history: GitHistory, snapshot: str) -> None:
    history.restore(snapshot)
    if history.layout.workspace.is_dir():
        lay_out_scripts(history.layout)


def _roll_back(history: GitHistory, snapshot: str, log: LogSink) -> bool:
    try:
        _restore(history, snapshot)
    except (HistoryCaptureError, OSError, ValueError) as exc:
        log("system", "error", f"Cannot roll the REE back after a failed capture: {exc}")
        return False
    return True


def step_evidence(layout: ReeLayout, log: LogSink) -> dict[str, str] | None:
    if not layout.manifest.is_file():
        return None
    try:
        report = audit(ReeDirectory(layout).read_ree())
    except Exception as exc:  # noqa: BLE001
        log("system", "warn", f"Step evidence was not recorded: {exc}")
        return None
    standing = {
        name: step.evidence
        for name in (
            "acquire_source",
            "evaluate_reproducibility",
            "observe_hardware",
            "check_working_environment",
            "build_experiment_environment",
            "generate_sbom",
            "cross_check_sbom",
            "activate_experiment_environment",
        )
        if (step := getattr(report, name)) is not None
    }
    standing.update({f"run_experiment:{item.name}": item.run.evidence for item in report.experiments})
    return standing


def _references(record: OperationRecord, record_digest: str | None = None) -> HistoryReference:
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
            "record_digest": record_digest,
            "drift_after": [item.model_dump() for item in record.drift_after],
        }
    )
