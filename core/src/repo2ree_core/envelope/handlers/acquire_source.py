"""Handler for the acquire_source operation.

Clones or downloads source into the declared destination directory.
For git sources, the resolved HEAD commit is recorded in ActionResult.outputs
as ``resolved_commit`` — the reproducibility receipt for the source.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from repo2ree_core.container.run_script import CancelCheck, LogSink, format_command, stream_output
from repo2ree_core.storage.extract import safe_extract_tar, safe_extract_zip
from repo2ree_core.storage.fetch import download_or_copy
from repo2ree_core.storage.store import SubtreeStore
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_protocol.result import ActionResult


def handle_acquire_source(
    args: AcquireSourceArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "acquire_source canceled before start")
        return ActionResult(status="canceled")

    log(
        "system",
        "info",
        f"acquire_source: {args.source_type} {args.origin_url} → {args.dest}",
    )
    SubtreeStore(args.dest).clear()
    args.dest.mkdir(parents=True, exist_ok=True)

    if args.source_type == "git":
        return _acquire_git(args, log=log, is_canceled=is_canceled)
    return _acquire_archive(args, log=log, is_canceled=is_canceled)


def _acquire_git(
    args: AcquireSourceArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    clone_cmd = ["git", "clone", "--depth", "1", args.origin_url, str(args.dest)]
    log("system", "info", format_command(clone_cmd))
    result = subprocess.run(clone_cmd, capture_output=True, text=True)
    stream_output(log, result)
    if result.returncode != 0:
        return ActionResult(status="failed", exit_code=result.returncode)

    if is_canceled():
        log("system", "warn", "acquire_source canceled after clone")
        return ActionResult(status="canceled")

    rev_result = subprocess.run(
        ["git", "-C", str(args.dest), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    resolved_commit = rev_result.stdout.strip() if rev_result.returncode == 0 else ""

    log("system", "info", f"resolved commit: {resolved_commit}")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={"resolved_commit": resolved_commit, "origin_url": args.origin_url},
    )


def _acquire_archive(
    args: AcquireSourceArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "source.archive"

        log("system", "info", f"downloading {args.origin_url}")
        try:
            download_or_copy(args.origin_url, archive)
        except Exception as exc:
            log("system", "error", f"download failed: {exc}")
            return ActionResult(status="failed", exit_code=1)

        if is_canceled():
            log("system", "warn", "acquire_source canceled after download")
            return ActionResult(status="canceled")

        log("system", "info", f"extracting to {args.dest}")
        try:
            if args.source_type == "zip":
                safe_extract_zip(archive, args.dest)
            else:
                safe_extract_tar(archive, args.dest)
        except Exception as exc:
            log("system", "error", f"extraction failed: {exc}")
            return ActionResult(status="failed", exit_code=1)

    log("system", "info", "acquire_source succeeded")
    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs={"origin_url": args.origin_url},
    )
