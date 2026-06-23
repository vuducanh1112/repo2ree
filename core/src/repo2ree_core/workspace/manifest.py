"""Pure construction of the published REE manifest.

The manifest is the JSON payload written to ``manifest.json`` and embedded
into the downloadable bundle as ``ree/ree.json``. It is computed from a
:class:`~repo2ree_core.domain.ree_intent.ReeIntent` and a
:class:`~repo2ree_core.domain.ree_session.ReeSession` together with the
surrounding workspace metadata. This module performs no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from repo2ree_core.domain.ree_intent import REE_MANIFEST_VERSION, ReeIntent
from repo2ree_core.domain.ree_session import ReeSession

_SESSION_MANIFEST_EXCLUDE = {"detected_dependencies", "uploaded_archive", "source_resolved_commit"}


def build_manifest_payload(
    intent: ReeIntent,
    session: ReeSession,
    *,
    ree_id: str,
) -> dict[str, Any]:
    """Build the published manifest from ``intent`` and ``session``."""
    return {
        **intent.model_dump(),
        **session.model_dump(exclude=_SESSION_MANIFEST_EXCLUDE),
        "ree_version": REE_MANIFEST_VERSION,
        "name": intent.name or f"workspace-{ree_id[:8]}",
    }


def build_draft_manifest_payload(
    metadata: Mapping[str, Any],
    *,
    workspace_files: Sequence[Mapping[str, Any]],
    ree_files: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the live, read-only manifest projection for an editable REE.

    Unlike the sealed manifest sidecar, this payload is not a source of truth
    and is not written to disk. It gives clients a stable overview assembled
    from the current metadata and file inventory.
    """
    ree_id = str(metadata.get("reeId") or "")
    intent = ReeIntent.from_metadata(metadata)
    session = ReeSession.from_metadata(metadata)
    manifest = build_manifest_payload(intent, session, ree_id=ree_id)

    return {
        **manifest,
        "manifest_state": "draft",
        "ree_id": ree_id,
        "status": str(metadata.get("status") or "draft"),
        "created_at": metadata.get("createdAt"),
        "updated_at": metadata.get("updatedAt"),
        "file_inventory": {
            "workspace": [_file_inventory_entry(file) for file in workspace_files],
            "overlay": [_file_inventory_entry(file) for file in _files_under(ree_files, "overlay")],
            "artifacts": [_file_inventory_entry(file) for file in _files_under(ree_files, "artifacts")],
        },
    }


def _files_under(
    files: Sequence[Mapping[str, Any]],
    top_level_dir: str,
) -> list[Mapping[str, Any]]:
    prefix = f"{top_level_dir}/"
    return [file for file in files if str(file.get("path") or "").startswith(prefix)]


def _file_inventory_entry(file: Mapping[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": str(file.get("path") or ""),
        "kind": str(file.get("kind") or ""),
    }
    if file.get("tag") is not None:
        entry["tag"] = str(file.get("tag") or "")
    if file.get("size") is not None:
        entry["size"] = file.get("size")
    return entry
