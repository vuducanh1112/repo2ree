"""Remove acquired source bytes and source-derived evidence from a draft REE."""

from __future__ import annotations

import shutil

from repo2ree_core.domain.ree.transitions import ReePreconditionError, clear_source, revision_of
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author.materialize_workspace import materialize_workspace
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import load_ree, save_ree
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def handle_remove_source(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "metadata not found — was init-ree run?")

    try:
        ree = load_ree(layout, store)
        before_revision = revision_of(ree)
        updated = clear_source(ree)
    except ReePreconditionError as exc:
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        return failed_from_exception(exc, f"remove_source failed: {exc}")

    log("system", "info", "remove_source: clearing acquired and source-derived content")
    try:
        store.upstream.clear()
        store.artifacts.clear()
        shutil.rmtree(layout.results, ignore_errors=True)
        layout.results.mkdir(parents=True, exist_ok=True)
        store.workspace.clear()
        for path in (
            layout.snapshot_archive,
            layout.acquire_script,
            layout.materialize_script,
            layout.sealed_archive,
        ):
            path.unlink(missing_ok=True)
        save_ree(layout, store, updated, expected_revision=before_revision)
    except Exception as exc:
        log("system", "error", f"remove_source failed: {exc}")
        return failed_from_exception(exc, f"remove_source failed: {exc}")

    materialized = materialize_workspace(layout, snapshot_digest=None, log=log, is_canceled=is_canceled)
    if materialized.status != "succeeded":
        return materialized
    log("system", "info", "remove_source succeeded; authored recipe files were preserved")
    return ActionResult(status="succeeded", exit_code=0)
