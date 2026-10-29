"""Optimistic concurrency for authored workspace files."""

from __future__ import annotations

from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import VersionConflictOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import digest_bytes


def workspace_content_etag(store: ReeDirectory, path: str) -> str | None:
    if not store.workspace.is_file(path):
        return None
    return digest_bytes(store.workspace.read_bytes(path))


def check_expected_etag(
    store: ReeDirectory,
    path: str,
    expected: str,
    *,
    log: LogSink,
) -> ActionResult | None:
    if not expected:
        return None
    actual = workspace_content_etag(store, path)
    if expected == actual:
        return None
    log("system", "error", f"etag mismatch for {path}: expected {expected}, actual {actual}")
    return ActionResult.failed(
        "conflict",
        f"etag mismatch for {path}: expected {expected}, actual {actual}",
        retryable=True,
        outputs=VersionConflictOutputs(
            path=path,
            expected_version=expected,
            actual_version=actual,
        ).as_outputs(),
    )
