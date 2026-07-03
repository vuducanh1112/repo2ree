"""Handler for the write_file operation.

Writes content into /ree/overlay/<path> and mirrors it to /ree/workspace/<path>.
Mirrors the host-side write_file_content behaviour exactly.
"""

from __future__ import annotations

from repo2ree_core.run_script import CancelCheck
from repo2ree_core.storage.layout import ReeLayout, validate_relative_path
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.command import WriteFileArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_write_file(
    args: WriteFileArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "write_file canceled before start")
        return ActionResult(status="canceled")

    try:
        validate_relative_path(args.path)
    except ValueError as exc:
        log("system", "error", f"invalid path: {exc}")
        return ActionResult(status="failed", exit_code=1)

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    log("system", "info", f"write_file: {args.path}")
    try:
        store.overlay.write_text(args.path, args.content)
        store.workspace.write_text(args.path, args.content)
    except Exception as exc:
        log("system", "error", f"write_file failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    return ActionResult(status="succeeded", exit_code=0)
