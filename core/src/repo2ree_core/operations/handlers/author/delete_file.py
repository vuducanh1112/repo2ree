"""Handler for the delete_file operation.

Removes a path from /ree/overlay/ and either restores it from upstream
(if the file originated there) or removes it from workspace entirely.
Mirrors the host-side delete_file_content behaviour exactly.
"""

from __future__ import annotations

from repo2ree_core.domain.ree.transitions import ReePreconditionError, replace_definition, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author.definition_authoring import rehydrate_after_file_mutation
from repo2ree_core.operations.handlers.author.file_concurrency import check_expected_etag
from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import ReeRevisionConflictError, load_ree, save_ree
from repo2ree_protocol.command import DeleteFileArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_delete_file(
    args: DeleteFileArgs,
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
    store = ReeDirectory(layout)
    if not store.record_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")
    try:
        ree = load_ree(layout, store)
        if ree.seal is not None:
            raise ReePreconditionError("a sealed REE cannot edit authored files")
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load REE: {exc}")

    if not store.workspace.is_file(args.path):
        log("system", "error", f"file not found in workspace: {args.path}")
        return ActionResult.failed("precondition", f"file not found in workspace: {args.path}")

    conflict = check_expected_etag(store, args.path, args.expected_etag, log=log)
    if conflict is not None:
        return conflict
    if is_canceled():
        return ActionResult(status="canceled")

    log("system", "info", f"delete_file: {args.path}")
    old_overlay = store.overlay.read_bytes(args.path) if store.overlay.is_file(args.path) else None
    old_workspace = store.workspace.read_bytes(args.path)
    before_revision = revision_of(ree)
    try:
        store.overlay.delete_if_exists(args.path)
        if store.upstream.is_file(args.path):
            store.workspace.write_bytes(args.path, store.upstream.read_bytes(args.path))
        else:
            store.workspace.delete_if_exists(args.path)
        definition = rehydrate_after_file_mutation(ree.subject.definition, args.path, layout)
        save_ree(
            layout,
            store,
            replace_definition(ree, definition),
            expected_revision=before_revision,
        )
    except ReeRevisionConflictError as exc:
        _restore_file(store, args.path, old_overlay=old_overlay, old_workspace=old_workspace)
        return ActionResult.failed("conflict", str(exc), retryable=True)
    except Exception as exc:
        _restore_file(store, args.path, old_overlay=old_overlay, old_workspace=old_workspace)
        log("system", "error", f"delete_file failed: {exc}")
        return failed_from_exception(exc, f"delete_file failed: {exc}")

    return ActionResult(status="succeeded", exit_code=0)


def _restore_file(
    store: ReeDirectory,
    path: str,
    *,
    old_overlay: bytes | None,
    old_workspace: bytes,
) -> None:
    if old_overlay is None:
        store.overlay.delete_if_exists(path)
    else:
        store.overlay.write_bytes(path, old_overlay)
    store.workspace.write_bytes(path, old_workspace)
