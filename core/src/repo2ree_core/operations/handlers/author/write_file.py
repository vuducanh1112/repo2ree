"""Handler for the write_file operation.

Writes content into /ree/overlay/<path> and mirrors it to /ree/workspace/<path>.
Mirrors the host-side write_file_content behaviour exactly.
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
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")
    try:
        ree = load_ree(layout, store)
        if ree.seal is not None:
            raise ReePreconditionError("a sealed REE cannot edit authored files")
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        return failed_from_exception(exc, f"failed to load REE: {exc}")

    conflict = check_expected_etag(store, args.path, args.expected_etag, log=log)
    if conflict is not None:
        return conflict
    if is_canceled():
        return ActionResult(status="canceled")

    log("system", "info", f"write_file: {args.path}")
    old_overlay = store.overlay.read_bytes(args.path) if store.overlay.is_file(args.path) else None
    old_workspace = store.workspace.read_bytes(args.path) if store.workspace.is_file(args.path) else None
    before_revision = revision_of(ree)
    try:
        store.overlay.write_text(args.path, args.content)
        store.workspace.write_text(args.path, args.content)
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
        log("system", "error", f"write_file failed: {exc}")
        return failed_from_exception(exc, f"write_file failed: {exc}")

    return ActionResult(status="succeeded", exit_code=0)


def _restore_file(
    store: ReeDirectory,
    path: str,
    *,
    old_overlay: bytes | None,
    old_workspace: bytes | None,
) -> None:
    if old_overlay is None:
        store.overlay.delete_if_exists(path)
    else:
        store.overlay.write_bytes(path, old_overlay)
    if old_workspace is None:
        store.workspace.delete_if_exists(path)
    else:
        store.workspace.write_bytes(path, old_workspace)
