"""Handler for the acquire_source operation.

Populates the upstream directory with the canonical source by running the
generated ``acquire_source.sh`` (the single, shared acquire muscle): it extracts
the frozen snapshot when present, otherwise fetches the recorded origin. The
resolved-commit receipt is settled downstream by ``update_source_metadata``,
which reads HEAD off the acquired tree and persists it onto the intent.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.authoring.script_generation.acquire_source import build_acquire_sh
from repo2ree_core.evidence.receipts.models import AcquireSourceReceipt, receipt_envelope
from repo2ree_core.evidence.receipts.store import record_receipt
from repo2ree_core.execution.process import (
    CancelCheck,
    format_command,
    run_streaming_process,
)
from repo2ree_core.ree.layout import ACQUIRE_SCRIPT_FILENAME, ReeLayout
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class AcquireSourceOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_url: str


def _write_acquire_script(args: AcquireSourceArgs, *, log: LogSink, layout: ReeLayout) -> Path:
    """Persist ``acquire_source.sh`` (baked with this source's identity) in the REE.

    Written to the reserved root path so it is sealed into the bundle and run.sh
    can call the very same file. Acquire only ever runs inside a workbench REE,
    so the REE root is always present. The SWHID is unknown at authoring time
    (it is computed after acquisition); seal regenerates the script with it baked
    in for the bundle.
    """
    layout.acquire_script.write_bytes(
        build_acquire_sh(origin_url=args.origin_url, source_type=args.source_type or "", revision=args.revision)
    )
    log("system", "info", f"wrote acquire script → {ACQUIRE_SCRIPT_FILENAME}")
    return layout.acquire_script


def handle_acquire_source(
    args: AcquireSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    timer = OperationTimer.start()
    layout = ReeLayout.in_workbench()
    log(
        "system",
        "info",
        f"acquire_source: {args.source_type or 'snapshot'} {args.origin_url} → {layout.upstream}",
    )

    # The script owns the fixed REE layout paths and the snapshot-vs-fetch
    # decision; the handler only records identity afterwards (the judgement).
    script = _write_acquire_script(args, log=log, layout=layout)
    cmd = ["sh", str(script)]
    if args.refetch:
        cmd.append("--refetch")
    log("system", "info", format_command(cmd))
    result = run_streaming_process(cmd, log=log, is_canceled=is_canceled)

    if result.canceled or is_canceled():
        timing = timer.finish()
        log(
            "system",
            "warn",
            f"acquire_source canceled in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )
        return ActionResult(status="canceled")
    if result.returncode != 0:
        timing = timer.finish()
        log(
            "system",
            "error",
            f"acquire_source failed in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )
        return ActionResult.failed(
            "execution",
            f"acquire script exited {result.returncode}",
            exit_code=result.returncode or 1,
        )

    timing = timer.finish()
    record_receipt(
        layout,
        AcquireSourceReceipt(
            **receipt_envelope(run_id, timing, "succeeded"),
            origin_url=args.origin_url,
            source_type=args.source_type or "",
            revision=args.revision or "",
        ),
        log=log,
    )
    log(
        "system",
        "info",
        f"acquire_source succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=AcquireSourceOutputs(origin_url=args.origin_url).model_dump(),
    )
