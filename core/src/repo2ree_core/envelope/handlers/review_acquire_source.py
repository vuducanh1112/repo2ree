"""Acquire and verify source identity inside an isolated review attempt."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.receipts import AcquireSourceReceipt, receipt_run_id
from repo2ree_core.ree_scripts.acquire_source import build_acquire_sh
from repo2ree_core.reviews import (
    ReviewRecord,
    SourceComparison,
    compare_source_swhids,
    write_review_record,
    write_review_source_evidence,
)
from repo2ree_core.run_script import CancelCheck, format_command, run_streaming_process
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import ReviewAcquireSourceArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewAcquireSourceOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: AcquireSourceReceipt
    comparison: SourceComparison


def handle_review_acquire_source(
    args: ReviewAcquireSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(args.review_id)
    intent = ReeStore(ree_layout).read_intent()
    timer = OperationTimer.start()

    started = ReviewRecord(
        review_id=args.review_id,
        created_at=timer.started_at,
        updated_at=timer.started_at,
        status="running",
    )
    write_review_record(review_layout, started)

    def stop(status: str, message: str) -> ActionResult:
        timing = timer.finish()
        terminal_status = "canceled" if status == "canceled" else "failed"
        write_review_record(
            review_layout,
            started.model_copy(
                update={
                    "updated_at": timing.finished_at,
                    "status": terminal_status,
                    "failure": message,
                }
            ),
        )
        level = "warn" if terminal_status == "canceled" else "error"
        log("system", level, f"review source acquisition {terminal_status}: {message}")
        if terminal_status == "canceled":
            return ActionResult(status="canceled", outputs={"review_id": args.review_id})
        return ActionResult.failed("precondition", message)

    if is_canceled():
        return stop("canceled", "canceled before source acquisition")
    if not intent.origin_url or intent.source_type not in {"git", "tarball", "zip"}:
        return stop("failed", "The author baseline has no independently acquirable source origin")

    review_layout.root.mkdir(parents=True, exist_ok=True)
    review_layout.acquire_script.write_bytes(
        build_acquire_sh(
            origin_url=intent.origin_url,
            source_type=intent.source_type,
            revision=intent.revision,
            swhid=intent.swhid,
        )
    )
    command = ["sh", str(review_layout.acquire_script)]
    log("system", "info", f"review {args.review_id}: acquiring source into {review_layout.upstream}")
    log("system", "info", format_command(command))
    result = run_streaming_process(command, log=log, is_canceled=is_canceled)
    if result.canceled or is_canceled():
        return stop("canceled", "source acquisition canceled")
    if result.returncode != 0:
        return stop("failed", f"acquire script exited {result.returncode}")

    observed_swhid = directory_swhid(review_layout.upstream)
    comparison = compare_source_swhids(intent.swhid, observed_swhid)
    timing = timer.finish()
    receipt = AcquireSourceReceipt(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status="succeeded",
        origin_url=intent.origin_url,
        source_type=intent.source_type,
        revision=intent.revision,
        expected_swhid=comparison.expected_swhid,
        observed_swhid=comparison.observed_swhid,
    )
    write_review_source_evidence(review_layout, receipt, comparison)
    write_review_record(
        review_layout,
        started.model_copy(
            update={
                "updated_at": timing.finished_at,
                "status": "completed",
                "source_receipt": receipt,
                "source_comparison": comparison,
            }
        ),
    )
    log(
        "system",
        "info" if comparison.verdict == "identical" else "warn",
        f"source comparison {comparison.verdict}: expected {comparison.expected_swhid or 'none'}, "
        f"observed {comparison.observed_swhid or 'none'}",
    )
    log(
        "system",
        "info",
        f"review source acquisition succeeded in {format_duration_ms(timing.duration_ms)} "
        f"(duration_ms={timing.duration_ms})",
    )
    outputs = ReviewAcquireSourceOutputs(
        review_id=args.review_id,
        receipt=receipt,
        comparison=comparison,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))
