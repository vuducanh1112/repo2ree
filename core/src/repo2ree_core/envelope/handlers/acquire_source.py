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

from repo2ree_core.receipts import AcquireSourceReceipt, receipt_run_id, record_receipt
from repo2ree_core.ree_scripts.acquire_source import build_acquire_sh
from repo2ree_core.run_script import (
    CancelCheck,
    format_command,
    run_streaming_process,
)
from repo2ree_core.storage.layout import ACQUIRE_SCRIPT_FILENAME, ReeLayout
from repo2ree_core.time_utils import utc_now
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
    if is_canceled():
        log("system", "warn", "acquire_source canceled before start")
        return ActionResult(status="canceled")

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
        log("system", "warn", "acquire_source canceled")
        return ActionResult(status="canceled")
    if result.returncode != 0:
        return ActionResult(status="failed", exit_code=result.returncode or 1)

    record_receipt(
        layout,
        AcquireSourceReceipt(
            run_id=receipt_run_id(run_id),
            recorded_at=utc_now(),
            status="succeeded",
            origin_url=args.origin_url,
            source_type=args.source_type or "",
            revision=args.revision or "",
        ),
        log=log,
    )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=AcquireSourceOutputs(origin_url=args.origin_url).model_dump(),
    )
