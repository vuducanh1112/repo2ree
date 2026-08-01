"""Workspace-file inventory rules.

Pure helpers that decide how the workspace subtree is enumerated and
presented to clients: which on-disk names are reserved system files,
which file contents are small enough to inline in API responses, and
how a path is classified — plus the entry models the enumeration
produces, so producers and the API contract share one shape.

No filesystem I/O.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

MAX_INLINE_TEXT_BYTES = 1024 * 1024
MAX_INLINE_SBOM_BYTES = 8 * 1024 * 1024

WorkspaceFileKind = Literal["source", "generated"]


class WorkspaceFile(BaseModel):
    """One workspace-subtree file as the enumeration presents it.

    ``content`` is the inlined text when the file is small enough (see
    :func:`should_inline_file_content`) and the caller asked for content;
    ``None`` otherwise.
    """

    model_config = ConfigDict(extra="forbid")

    path: str
    kind: WorkspaceFileKind
    size: int
    content: str | None = None


class ReeFile(BaseModel):
    """One file under the REE root (upstream/overlay/artifacts/…)."""

    model_config = ConfigDict(extra="forbid")

    path: str
    kind: Literal["ree"] = "ree"
    tag: str
    size: int
    content: str | None = None


def is_upload_staging_name(name: str) -> bool:
    """True for filenames that belong to the upload staging area."""
    return name.startswith(".upload.")


def is_metadata_file_name(name: str) -> bool:
    """True for the workspace metadata sidecar filename."""
    return name == ".workspace.json"


def is_reserved_workspace_filename(name: str) -> bool:
    """True for any filename the workspace API treats as a system file.

    Currently: the metadata sidecar and upload-staging blobs. Workspace
    enumeration and ad-hoc path access both reject these names.
    """
    return name.startswith((".workspace", ".upload."))


def should_inline_file_content(relative_path: str, size: int) -> bool:
    """Whether a file's text content is small enough to embed inline."""
    lower_path = relative_path.lower()
    if lower_path.endswith("sbom.json") and size > MAX_INLINE_SBOM_BYTES:
        return False
    return size <= MAX_INLINE_TEXT_BYTES


def classify_file_kind(relative_path: str) -> WorkspaceFileKind:
    """Classify a workspace-relative path into a coarse kind.

    Currently all workspace files are classified as ``"source"``. The
    function exists so callers can rely on a single classification point
    even as the rules evolve.
    """
    _ = relative_path
    return "source"
