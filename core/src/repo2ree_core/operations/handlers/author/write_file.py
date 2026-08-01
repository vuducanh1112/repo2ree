"""Handler for the write_file operation.

Writes content into /ree/overlay/<path> and mirrors it to /ree/workspace/<path>.
Mirrors the host-side write_file_content behaviour exactly.
"""

from __future__ import annotations

from repo2ree_core.domain.primitives import ReePath
from repo2ree_core.domain.ree_transitions import write_file
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.steps.author import check_expected_etag
from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.repository import load_ree
from repo2ree_core.ree.store import ReeStore
from repo2ree_protocol.command import WriteFileArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_write_file(
    args: WriteFileArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    try:
        validate_relative_path(args.path)
    except ValueError as exc:
        log("system", "error", f"invalid path: {exc}")
        return ActionResult.failed("validation", f"invalid path: {exc}")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    conflict = check_expected_etag(store, args.path, args.expected_etag, log=log)
    if conflict is not None:
        return conflict

    log("system", "info", f"write_file: {args.path}")
    try:
        transition = write_file(load_ree(layout, store), ReePath(args.path), args.content.encode("utf-8"))
        store.overlay.write_text(transition.changed_file.path, args.content)
        store.workspace.write_text(transition.changed_file.path, args.content)
    except Exception as exc:
        log("system", "error", f"write_file failed: {exc}")
        return failed_from_exception(exc, f"write_file failed: {exc}")

    return ActionResult(status="succeeded", exit_code=0)
