"""Workspace-file inventory rules.

Pure helpers that decide how the workspace subtree is enumerated and
presented to clients: which on-disk names are reserved system files,
which file contents are small enough to inline in API responses, and
how a path is classified.

No filesystem I/O.
"""

from __future__ import annotations

MAX_INLINE_TEXT_BYTES = 1024 * 1024
MAX_INLINE_SBOM_BYTES = 8 * 1024 * 1024


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
    return name.startswith(".workspace") or name.startswith(".upload.")


def should_inline_file_content(relative_path: str, size: int) -> bool:
    """Whether a file's text content is small enough to embed inline."""
    lower_path = relative_path.lower()
    if lower_path.endswith("sbom.json") and size > MAX_INLINE_SBOM_BYTES:
        return False
    if size > MAX_INLINE_TEXT_BYTES:
        return False
    return True


def classify_file_kind(relative_path: str) -> str:
    """Classify a workspace-relative path into a coarse kind.

    Currently all workspace files are classified as ``"source"``. The
    function exists so callers can rely on a single classification point
    even as the rules evolve.
    """
    _ = relative_path
    return "source"
