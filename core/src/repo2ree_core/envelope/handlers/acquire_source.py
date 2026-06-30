"""Handler for the acquire_source operation.

Populates the upstream directory with the canonical source by running the
generated ``acquire_source.sh`` (the single, shared acquire muscle): it extracts
the frozen snapshot when present, otherwise fetches the recorded origin. For git
sources the resolved HEAD commit is recorded in ActionResult.outputs as
``resolved_commit`` — the reproducibility receipt for the source.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from repo2ree_core.container.run_script import (
    CancelCheck,
    LogSink,
    format_command,
    run_streaming_process,
)
from repo2ree_core.ree_scripts.acquire_source import build_acquire_sh
from repo2ree_core.storage.layout import ACQUIRE_SCRIPT_FILENAME, ReeLayout
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_protocol.result import ActionResult


def _write_acquire_script(args: AcquireSourceArgs, *, log: LogSink, layout: ReeLayout) -> Path:
    """Persist ``acquire_source.sh`` (baked with this source's identity) in the REE.

    Written to the reserved root path so it is sealed into the bundle and run.sh
    can call the very same file. Acquire only ever runs inside a workbench REE,
    so the REE root is always present. The SWHID is unknown at authoring time
    (it is computed after acquisition); seal regenerates the script with it baked
    in for the bundle.
    """
    layout.acquire_script.write_bytes(build_acquire_sh(origin_url=args.origin_url, source_type=args.source_type or ""))
    log("system", "info", f"wrote acquire script → {ACQUIRE_SCRIPT_FILENAME}")
    return layout.acquire_script


def handle_acquire_source(
    args: AcquireSourceArgs,
    *,
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

    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={"resolved_commit": _resolved_commit(args, dest=layout.upstream), "origin_url": args.origin_url},
    )


def _resolved_commit(args: AcquireSourceArgs, *, dest: Path) -> str:
    """The HEAD commit of a freshly acquired git source — its identity receipt.

    Empty for non-git sources, or when the acquired tree carries no git history
    (e.g. extracted from a snapshot that did not preserve ``.git``).
    """
    if args.source_type != "git":
        return ""
    rev = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return rev.stdout.strip() if rev.returncode == 0 else ""
