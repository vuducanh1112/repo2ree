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
from repo2ree_core.workspace.model import WorkspaceMetadata

_SESSION_MANIFEST_EXCLUDE = {"detected_dependencies", "uploaded_archive", "source_resolved_commit"}


def build_manifest_payload(
    intent: ReeIntent,
    session: ReeSession,
    *,
    ree_id: str,
    consistency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the published manifest from ``intent`` and ``session``.

    ``consistency`` is the seal-time per-step freshness report (recorded
    receipts vs. the tree being sealed); present only on sealed manifests.
    """
    payload = {
        **intent.model_dump(),
        **session.model_dump(exclude=_SESSION_MANIFEST_EXCLUDE),
        "ree_version": REE_MANIFEST_VERSION,
        "name": intent.name or f"workspace-{ree_id[:8]}",
    }
    if consistency is not None:
        payload["consistency"] = consistency
    return payload


def split_manifest_payload(payload: Mapping[str, Any]) -> tuple[ReeIntent, ReeSession]:
    """Recover the intent and session a published manifest was built from.

    The inverse of :func:`build_manifest_payload`, used when an REE is loaded
    back from a downloaded bundle. Manifest-only keys (``ree_version``, the
    seal-time ``consistency`` report, and the draft projection's extras) are
    dropped, and the session fields the manifest never carries
    (``_SESSION_MANIFEST_EXCLUDE``) fall back to their defaults — they are
    authoring detail, not part of the published record.
    """
    version = payload.get("ree_version")
    if version != REE_MANIFEST_VERSION:
        raise ValueError(f"unsupported manifest version: {version!r} (expected {REE_MANIFEST_VERSION})")
    intent = ReeIntent.model_validate(_pick(payload, ReeIntent))
    session = ReeSession.model_validate(_pick(payload, ReeSession))
    return intent, session


def _pick(payload: Mapping[str, Any], model: type[ReeIntent] | type[ReeSession]) -> dict[str, Any]:
    """The subset of ``payload`` that ``model`` declares, keyed by field name."""
    return {key: value for key, value in payload.items() if key in model.model_fields}


def build_draft_manifest_payload(
    metadata: WorkspaceMetadata,
    *,
    workspace_files: Sequence[Mapping[str, Any]],
    ree_files: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the live, read-only manifest projection for an editable REE.

    Unlike the sealed manifest sidecar, this payload is not a source of truth
    and is not written to disk. It gives clients a stable overview assembled
    from the current metadata and file inventory.
    """
    manifest = build_manifest_payload(metadata.ree_intent, metadata.ree_session, ree_id=metadata.ree_id)

    return {
        **manifest,
        "manifest_state": "draft",
        "ree_id": metadata.ree_id,
        "status": metadata.status,
        "created_at": metadata.created_at,
        "updated_at": metadata.updated_at,
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
