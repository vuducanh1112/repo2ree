"""Handler for the acquire_source operation.

Populates the upstream directory with the canonical source by running the
generated ``acquire_source.sh`` (the single, shared acquire muscle): it extracts
the frozen snapshot when present, otherwise fetches the recorded origin.

Effect only. This step neither records a receipt nor touches REE state: it is
one muscle of the acquire lifecycle in
:mod:`repo2ree_core.operations.handlers.author.prepare_source`, which hydrates
the REE, decides the acquisition is legal, and commits everything the effects
produced in a single save. Dispatched on its own — as the reproducer's
``run.sh`` does — it is exactly what it looks like: a fetch into ``upstream/``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.authoring.script_generation.acquire_source import build_acquire_sh
from repo2ree_core.execution.process import (
    CancelCheck,
    StreamingProcessResult,
    format_command,
    run_streaming_process,
)
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ACQUIRE_SCRIPT_FILENAME, ReeLayout
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
    write_atomic(
        layout.acquire_script,
        build_acquire_sh(origin_url=args.origin_url, source_type=args.source_type or "", revision=args.revision),
    )
    log("system", "info", f"wrote acquire script → {ACQUIRE_SCRIPT_FILENAME}")
    return layout.acquire_script


def run_acquire_script(
    layout: ReeLayout,
    args: AcquireSourceArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> StreamingProcessResult:
    """Write the acquire script for this source and run it into ``upstream/``.

    The script owns the fixed REE layout paths and the snapshot-vs-fetch
    decision, so this only bakes in the source's identity and drives it.
    """
    log(
        "system",
        "info",
        f"acquire_source: {args.source_type or 'snapshot'} {args.origin_url} → {layout.upstream}",
    )
    script = _write_acquire_script(args, log=log, layout=layout)
    cmd = ["sh", str(script)]
    if args.refetch:
        cmd.append("--refetch")
    log("system", "info", format_command(cmd))
    return run_streaming_process(cmd, log=log, is_canceled=is_canceled)


def handle_acquire_source(
    args: AcquireSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    result = run_acquire_script(layout, args, log=log, is_canceled=is_canceled)

    if result.canceled or is_canceled():
        return ActionResult(status="canceled")
    if result.returncode != 0:
        return ActionResult.failed(
            "execution",
            f"acquire script exited {result.returncode}",
            exit_code=result.returncode or 1,
        )
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=AcquireSourceOutputs(origin_url=args.origin_url).model_dump(),
    )
