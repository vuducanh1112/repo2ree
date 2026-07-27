"""Handler for the delete_file operation.

Removes a path from /ree/overlay/ and either restores it from upstream
(if the file originated there) or removes it from workspace entirely.
Mirrors the host-side delete_file_content behaviour exactly.
"""

from __future__ import annotations

from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.operations.handlers._common import check_expected_etag
from repo2ree_core.ree.layout import ReeLayout, validate_relative_path
from repo2ree_core.ree.store import ReeStore
from repo2ree_protocol.command import DeleteFileArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_delete_file(
    args: DeleteFileArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "delete_file canceled before start")
        return ActionResult(status="canceled")

    try:
        validate_relative_path(args.path)
    except ValueError as exc:
        log("system", "error", f"invalid path: {exc}")
        return ActionResult.failed("validation", f"invalid path: {exc}")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.workspace.is_file(args.path):
        log("system", "error", f"file not found in workspace: {args.path}")
        return ActionResult.failed("precondition", f"file not found in workspace: {args.path}")

    conflict = check_expected_etag(store, args.path, args.expected_etag, log=log)
    if conflict is not None:
        return conflict

    log("system", "info", f"delete_file: {args.path}")
    try:
        store.overlay.delete_if_exists(args.path)
        if store.upstream.is_file(args.path):
            store.workspace.write_bytes(args.path, store.upstream.read_bytes(args.path))
        else:
            store.workspace.delete_if_exists(args.path)
    except Exception as exc:
        log("system", "error", f"delete_file failed: {exc}")
        return ActionResult.failed("internal", f"delete_file failed: {exc}")

    return ActionResult(status="succeeded", exit_code=0)
