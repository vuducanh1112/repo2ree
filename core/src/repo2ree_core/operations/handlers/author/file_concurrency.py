"""Optimistic concurrency for authored workspace files."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_bytes
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class VersionConflictOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: Literal["version_conflict"] = "version_conflict"
    path: str | None = None
    expected_version: str
    actual_version: str | None

    def as_outputs(self) -> dict[str, Any]:
        return self.model_dump(exclude={"path"} if self.path is None else set())


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
