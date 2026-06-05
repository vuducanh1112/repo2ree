"""Read-only workspace/REE views and bundle assembly.

Imperative shell: functions perform filesystem I/O through ReeStore and
ReeLayout. No function reads from application settings; callers pass
``storage_root`` explicitly so this module can live in core.

These operations run **inside the workbench** (via the ``repo2ree`` CLI), which
is the single source of truth for REE state. Mutating workspace operations
(acquire, write, patch, upload, remove) are owned by the command-envelope
handlers in ``repo2ree_core.envelope.handlers``; this module only provides the
read views (``get_workspace``, ``read_file_bytes``) and the downloadable bundle
builder (``build_workspace_ree_archive``) the CLI exposes.

Layered on-disk layout (per REE):
  upstream/        extracted source, treated as read-only
  overlay/         user-added and tool-generated recipe files
  workspace/       materialized view (upstream merged with overlay)
  snapshot.tar.gz  frozen upstream archive
  .workspace.json  session metadata
  manifest.json    sealed REE spec sidecar
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.storage.layout import (
    ReeLayout,
    normalize_workspace_path,
    validate_relative_path,
)
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.bundle import (
    REE_ARTIFACTS_PREFIX,
    REE_MANIFEST_ENTRY_PATH,
    REE_OVERLAY_PREFIX,
    REE_SNAPSHOT_ENTRY_PATH,
    REE_WORKSPACE_DIR_ENTRY,
    ArtifactPlan,
    build_zip_bytes,
    plan_artifact_layout,
    rewrite_manifest_for_bundle,
    should_include_snapshot,
)
from repo2ree_core.workspace.inventory import (
    classify_file_kind,
    is_reserved_workspace_filename,
    should_inline_file_content,
)


# Deferred import to break the storage → workspace_ops → manifest → storage cycle.
def _build_manifest_payload(
    metadata: dict[str, Any],
    intent: ReeIntent,
    session: ReeSession,
    *,
    ree_id: str,
) -> dict[str, Any]:
    from repo2ree_core.workspace.manifest import build_manifest_payload

    return build_manifest_payload(metadata, intent, session, ree_id=ree_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _layout(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def _store(storage_root: Path, ree_id: str) -> ReeStore:
    return ReeStore(_layout(storage_root, ree_id))


def _validate_user_path(path: str) -> str:
    normalized = normalize_workspace_path(path)
    validate_relative_path(normalized)
    if is_reserved_workspace_filename(PurePosixPath(normalized).name):
        raise ValueError("Invalid workspace path")
    return normalized


def _intent_from_metadata(metadata: dict[str, Any]) -> ReeIntent:
    return ReeIntent.from_metadata(metadata)


def _session_from_metadata(metadata: dict[str, Any]) -> ReeSession:
    return ReeSession.from_metadata(metadata)


def _read_metadata(storage_root: Path, ree_id: str) -> dict[str, Any]:
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    return store.read_metadata_json()


def _list_tree_relpaths(root: Path) -> list[str]:
    """Sorted POSIX relative paths of every file beneath ``root`` (shell)."""
    if not root.is_dir():
        return []
    return sorted(
        fp.relative_to(root).as_posix() for fp in root.rglob("*") if fp.is_file()
    )


def _build_artifact_plan(
    layout: ReeLayout, intent: ReeIntent, *, include_runtime: bool
) -> ArtifactPlan:
    """Snapshot disk state and delegate layout decisions to the pure planner."""
    workspace_files = frozenset(_list_tree_relpaths(layout.workspace))
    on_disk_artifacts = _list_tree_relpaths(layout.artifacts)
    return plan_artifact_layout(
        on_disk_artifact_relpaths=on_disk_artifacts,
        workspace_runtime_path=intent.runtime,
        workspace_sbom_path=intent.sbom,
        workspace_files=workspace_files,
        runtime_included=include_runtime,
    )


def _bundle_entry_bytes(
    layout: ReeLayout,
    artifact_plan: ArtifactPlan,
    *,
    include_snapshot: bool,
    manifest_bytes: bytes,
) -> list[tuple[str, bytes]]:
    """Read bytes for every entry included in the bundle (shell)."""
    entries: list[tuple[str, bytes]] = [(REE_MANIFEST_ENTRY_PATH, manifest_bytes)]
    if include_snapshot and layout.snapshot_archive.exists():
        entries.append((REE_SNAPSHOT_ENTRY_PATH, layout.snapshot_archive.read_bytes()))
    entries.append((REE_OVERLAY_PREFIX, b""))
    for rel in _list_tree_relpaths(layout.overlay):
        entries.append(
            (f"{REE_OVERLAY_PREFIX}{rel}", (layout.overlay / rel).read_bytes())
        )
    entries.append((REE_ARTIFACTS_PREFIX, b""))
    for rel in artifact_plan.on_disk_relpaths:
        entries.append(
            (f"{REE_ARTIFACTS_PREFIX}{rel}", (layout.artifacts / rel).read_bytes())
        )
    for ws_rel, archive_name in sorted(artifact_plan.workspace_pulls.items()):
        entries.append(
            (
                f"{REE_ARTIFACTS_PREFIX}{archive_name}",
                (layout.workspace / ws_rel).read_bytes(),
            )
        )
    entries.append((REE_WORKSPACE_DIR_ENTRY, b""))
    return entries


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _iter_workspace_files(store: ReeStore):
    """Yield every regular file in the materialized workspace/ subtree."""
    root = store.layout.workspace
    if not root.exists():
        raise FileNotFoundError(f"REE {store.layout.root.name} not found")
    yield from (p for p in sorted(root.rglob("*")) if p.is_file())


def _workspace_files_with_content(
    storage_root: Path, ree_id: str
) -> list[dict[str, Any]]:
    store = _store(storage_root, ree_id)
    root = store.layout.workspace
    entries: list[dict[str, Any]] = []
    for fp in _iter_workspace_files(store):
        rel = fp.relative_to(root).as_posix()
        size = fp.stat().st_size
        entries.append(
            {
                "path": rel,
                "kind": classify_file_kind(rel),
                "size": size,
                "content": (
                    _read_text_if_possible(fp)
                    if should_inline_file_content(rel, size)
                    else None
                ),
            }
        )
    return entries


_REE_SUBTREE_TAGS: dict[str, str] = {
    "upstream": "Upstream",
    "overlay": "Overlay",
    "artifacts": "Artifact",
    "workspace": "Workspace",
}


def _ree_file_tag(rel: str) -> str:
    if rel == "manifest.json":
        return "Manifest"
    if rel.endswith(".zip") or rel.endswith(".tar.gz"):
        return "Archive"
    top, _, _ = rel.partition("/")
    return _REE_SUBTREE_TAGS.get(top, "REE")


def _workspace_ree_files_with_content(
    storage_root: Path, ree_id: str
) -> list[dict[str, Any]]:
    """Enumerate every file under the REE root, mirroring the on-disk layout."""
    layout = _layout(storage_root, ree_id)
    ree_root = layout.root
    if not ree_root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    ree_files: list[dict[str, Any]] = []
    for fp in sorted(ree_root.rglob("*")):
        if not fp.is_file():
            continue
        if is_reserved_workspace_filename(fp.name):
            continue
        rel_path = fp.relative_to(ree_root)
        if any(part.startswith(".upload.") for part in rel_path.parts):
            continue
        rel = rel_path.as_posix()
        size = fp.stat().st_size
        content = (
            _read_text_if_possible(fp)
            if should_inline_file_content(rel, size)
            else None
        )
        ree_files.append(
            {
                "path": rel,
                "kind": "ree",
                "tag": _ree_file_tag(rel),
                "size": size,
                "content": content,
            }
        )
    return ree_files


# ---------------------------------------------------------------------------
# Public operations (read views + bundle builder)
# ---------------------------------------------------------------------------


def get_workspace(
    storage_root: Path,
    ree_id: str,
    seed_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = seed_metadata or _read_metadata(storage_root, ree_id)
    detail = dict(metadata)
    detail["files"] = _workspace_files_with_content(storage_root, ree_id)
    detail["reeFiles"] = _workspace_ree_files_with_content(storage_root, ree_id)
    return detail


def read_file_bytes(storage_root: Path, ree_id: str, path: str) -> bytes:
    normalized = _validate_user_path(path)
    fp = _layout(storage_root, ree_id).workspace_file(normalized)
    if not fp.exists() or not fp.is_file():
        raise FileNotFoundError(path)
    return fp.read_bytes()


def build_workspace_ree_archive(
    storage_root: Path,
    ree_id: str,
    *,
    include_source: bool,
    include_runtime: bool,
) -> bytes:
    metadata = _read_metadata(storage_root, ree_id)
    layout = _layout(storage_root, ree_id)
    intent = _intent_from_metadata(metadata)
    session = _session_from_metadata(metadata).with_packaging(
        source_included=include_source, runtime_included=include_runtime
    )
    sidecar_manifest = _build_manifest_payload(metadata, intent, session, ree_id=ree_id)

    artifact_plan = _build_artifact_plan(
        layout, intent, include_runtime=include_runtime
    )
    include_snapshot = should_include_snapshot(
        source_included=include_source,
        source_snapshot_archive=session.source_snapshot_archive,
    )
    bundle_manifest = rewrite_manifest_for_bundle(
        sidecar_manifest, artifact_plan.manifest_remap
    )
    manifest_bytes = json.dumps(bundle_manifest, indent=2, sort_keys=True).encode(
        "utf-8"
    )
    entries = _bundle_entry_bytes(
        layout,
        artifact_plan,
        include_snapshot=include_snapshot,
        manifest_bytes=manifest_bytes,
    )
    store = _store(storage_root, ree_id)
    store.write_manifest(sidecar_manifest)
    return build_zip_bytes(entries)
