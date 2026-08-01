"""Pure construction of the published REE manifest.

The manifest is the JSON payload written to ``manifest.json`` and embedded
into the downloadable bundle as ``ree/ree.json``. It is computed from a
:class:`~repo2ree_core.domain.ree.intent.ReeIntent` and a
:class:`~repo2ree_core.domain.ree.state.ReeLifecycleState` together with the
surrounding workspace metadata. This module performs no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from repo2ree_core.domain.ree.intent import REE_MANIFEST_VERSION, ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.persistence.metadata import WorkspaceMetadata
from repo2ree_core.persistence.workspace.inventory import ReeFile, WorkspaceFile

_STATE_MANIFEST_EXCLUDE = {"detected_dependencies", "uploaded_archive", "source_resolved_commit"}


def build_manifest_payload(
    intent: ReeIntent,
    state: ReeLifecycleState,
    *,
    ree_id: str,
    consistency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the published manifest from ``intent`` and ``state``.

    ``consistency`` is the seal-time per-step freshness report (recorded
    receipts vs. the tree being sealed); present only on sealed manifests.
    """
    payload = {
        **intent.model_dump(),
        **state.model_dump(mode="json", exclude=_STATE_MANIFEST_EXCLUDE),
        "ree_version": REE_MANIFEST_VERSION,
        "name": intent.name or f"workspace-{ree_id[:8]}",
    }
    if consistency is not None:
        payload["consistency"] = consistency
    return payload


def split_manifest_payload(payload: Mapping[str, Any]) -> tuple[ReeIntent, ReeLifecycleState]:
    """Recover the intent and state a published manifest was built from.

    The inverse of :func:`build_manifest_payload`, used when an REE is loaded
    back from a downloaded bundle. Manifest-only keys (``ree_version``, the
    seal-time ``consistency`` report, and the draft projection's extras) are
    dropped, and the state fields the manifest never carries
    (``_STATE_MANIFEST_EXCLUDE``) fall back to their defaults — they are
    authoring detail, not part of the published record.
    """
    version = payload.get("ree_version")
    if version != REE_MANIFEST_VERSION:
        raise ValueError(f"unsupported manifest version: {version!r} (expected {REE_MANIFEST_VERSION})")
    intent = ReeIntent.model_validate(_pick(payload, ReeIntent))
    state = ReeLifecycleState.model_validate(_pick(payload, ReeLifecycleState))
    return intent, state


def _pick(payload: Mapping[str, Any], model: type[ReeIntent | ReeLifecycleState]) -> dict[str, Any]:
    """The subset of ``payload`` that ``model`` declares, keyed by field name."""
    return {key: value for key, value in payload.items() if key in model.model_fields}


def build_draft_manifest_payload(
    metadata: WorkspaceMetadata,
    *,
    workspace_files: Sequence[WorkspaceFile],
    ree_files: Sequence[ReeFile],
) -> dict[str, Any]:
    """Build the live, read-only manifest projection for an editable REE.

    Unlike the sealed manifest sidecar, this payload is not a source of truth
    and is not written to disk. It gives clients a stable overview assembled
    from the current metadata and file inventory.
    """
    manifest = build_manifest_payload(metadata.ree_intent, metadata.ree_state, ree_id=metadata.ree_id)

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


def _files_under(files: Sequence[ReeFile], top_level_dir: str) -> list[ReeFile]:
    prefix = f"{top_level_dir}/"
    return [file for file in files if file.path.startswith(prefix)]


def _file_inventory_entry(file: WorkspaceFile | ReeFile) -> dict[str, Any]:
    """One inventory row: what the file is and where, never its content."""
    entry: dict[str, Any] = {"path": file.path, "kind": file.kind}
    if isinstance(file, ReeFile):
        entry["tag"] = file.tag
    entry["size"] = file.size
    return entry
