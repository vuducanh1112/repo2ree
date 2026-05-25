"""Workspace and REE lifecycle operations.

Imperative shell: all functions perform filesystem I/O through ReeStore
and ReeLayout. No function reads from application settings; callers pass
``storage_root`` explicitly so this module can live in core.

Layered on-disk layout (per REE):
  upstream/        extracted source, treated as read-only
  overlay/         user-added and tool-generated recipe files
  workspace/       materialized view (upstream merged with overlay)
  upload-staging/  in-flight upload bytes
  snapshot.tar.gz  frozen upstream archive
  .workspace.json  session metadata
  manifest.json    sealed REE spec sidecar

On source acquisition, bytes go into ``upstream/`` and ``workspace/`` is
rebuilt from ``upstream/ + overlay/``. User file writes land in
``overlay/`` and are mirrored into ``workspace/`` so build operations
always see a merged, up-to-date view.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from repo2ree_core.domain.ree import REE
from repo2ree_core.storage.extract import (
    pack_directory_tar_gz,
    safe_extract_tar,
    safe_extract_zip,
)
from repo2ree_core.storage.fetch import download_or_copy
from repo2ree_core.storage.layout import (
    ReeLayout,
    normalize_workspace_path,
    validate_relative_path,
)
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.storage.tree import copy_tree_contents
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
    safe_filename,
    should_include_snapshot,
)
from repo2ree_core.workspace.inventory import (
    classify_file_kind,
    is_metadata_file_name,
    is_reserved_workspace_filename,
    should_inline_file_content,
)


# Deferred import to break the storage → workspace_ops → manifest → storage cycle.
def _build_manifest_payload(
    metadata: dict[str, Any], ree: REE, *, ree_id: str
) -> dict[str, Any]:
    from repo2ree_core.workspace.manifest import build_manifest_payload

    return build_manifest_payload(metadata, ree, ree_id=ree_id)


# Fields the caller may patch; backend-managed ones are excluded.
_DRAFT_PATCH_FIELDS: frozenset[str] = frozenset(
    field_name
    for field_name in REE.model_fields
    if field_name
    not in {
        "dependency_level",
        "environment_level",
        "machine_level",
        "sealed_at",
        "seal_hash",
        "source_available",
        "source_acquired_by",
        "uploaded_archive",
        "source_snapshot_archive",
        "source_snapshot_captured_at",
        "downloadable_files",
    }
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _layout(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def _store(storage_root: Path, ree_id: str) -> ReeStore:
    return ReeStore(_layout(storage_root, ree_id))


def _materialize_workspace(store: ReeStore) -> None:
    """Rebuild workspace/ as upstream/ merged with overlay/ (overlay wins)."""
    store.workspace.clear()
    store.workspace.ensure_root()
    if store.layout.upstream.is_dir():
        copy_tree_contents(store.layout.upstream, store.layout.workspace)
    if store.layout.overlay.is_dir():
        copy_tree_contents(store.layout.overlay, store.layout.workspace)


def _validate_user_path(path: str) -> str:
    """Normalize and structurally validate a user-supplied path.

    Returns the normalized path string. Raises ValueError for traversals,
    absolute paths, or reserved filenames.
    """
    normalized = normalize_workspace_path(path)
    validate_relative_path(normalized)
    if is_reserved_workspace_filename(PurePosixPath(normalized).name):
        raise ValueError("Invalid workspace path")
    return normalized


def _default_metadata(ree_id: str, name: str | None = None) -> dict[str, Any]:
    ts = _utc_now()
    workspace_name = name or f"workspace-{ree_id[:8]}"
    return {
        "reeId": ree_id,
        "externalRef": None,
        "name": workspace_name,
        "status": "draft",
        "createdAt": ts,
        "updatedAt": ts,
        "reeDraft": REE(name=workspace_name).model_dump(exclude_none=True),
        "source": None,
    }


def _ree_from_metadata(metadata: dict[str, Any]) -> REE:
    return REE.from_metadata(metadata)


def _read_metadata(storage_root: Path, ree_id: str) -> dict[str, Any]:
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    return store.read_metadata_json()


def _write_metadata(
    storage_root: Path, ree_id: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    _sync_downloadable_files(storage_root, ree_id, metadata)
    _persist_manifest_sidecar(storage_root, ree_id, metadata)
    metadata["updatedAt"] = _utc_now()
    _store(storage_root, ree_id).write_metadata_json(metadata)
    return metadata


def _list_tree_relpaths(root: Path) -> list[str]:
    """Sorted POSIX relative paths of every file beneath ``root`` (shell)."""
    if not root.is_dir():
        return []
    return sorted(
        fp.relative_to(root).as_posix() for fp in root.rglob("*") if fp.is_file()
    )


def _build_artifact_plan(layout: ReeLayout, ree: REE) -> ArtifactPlan:
    """Snapshot disk state and delegate layout decisions to the pure planner."""
    workspace_files = frozenset(_list_tree_relpaths(layout.workspace))
    on_disk_artifacts = _list_tree_relpaths(layout.artifacts)
    return plan_artifact_layout(
        on_disk_artifact_relpaths=on_disk_artifacts,
        workspace_runtime_path=ree.runtime,
        workspace_sbom_path=ree.sbom,
        workspace_files=workspace_files,
        runtime_included=ree.runtime_included,
    )


def _bundle_archive_paths(
    layout: ReeLayout, artifact_plan: ArtifactPlan, *, include_snapshot: bool
) -> list[str]:
    """Archive paths that would appear in the bundle, without reading bytes."""
    paths = [REE_MANIFEST_ENTRY_PATH]
    if include_snapshot and layout.snapshot_archive.exists():
        paths.append(REE_SNAPSHOT_ENTRY_PATH)
    paths.append(REE_OVERLAY_PREFIX)
    for rel in _list_tree_relpaths(layout.overlay):
        paths.append(f"{REE_OVERLAY_PREFIX}{rel}")
    paths.append(REE_ARTIFACTS_PREFIX)
    for rel in artifact_plan.on_disk_relpaths:
        paths.append(f"{REE_ARTIFACTS_PREFIX}{rel}")
    for archive_name in sorted(artifact_plan.workspace_pulls.values()):
        paths.append(f"{REE_ARTIFACTS_PREFIX}{archive_name}")
    paths.append(REE_WORKSPACE_DIR_ENTRY)
    return paths


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


def _sync_downloadable_files(
    storage_root: Path, ree_id: str, metadata: dict[str, Any]
) -> None:
    layout = _layout(storage_root, ree_id)
    ree = _ree_from_metadata(metadata)
    manifest = _build_manifest_payload(metadata, ree, ree_id=ree_id)
    artifact_plan = _build_artifact_plan(layout, ree)
    ree_draft = dict(metadata.get("reeDraft") or {})
    ree_draft["downloadable_files"] = _bundle_archive_paths(
        layout,
        artifact_plan,
        include_snapshot=should_include_snapshot(
            source_included=bool(manifest.get("source_included")),
            source_snapshot_archive=manifest.get("source_snapshot_archive"),
        ),
    )
    metadata["reeDraft"] = ree_draft


def _persist_manifest_sidecar(
    storage_root: Path, ree_id: str, metadata: dict[str, Any]
) -> None:
    ree = _ree_from_metadata(metadata)
    manifest = _build_manifest_payload(metadata, ree, ree_id=ree_id)
    _store(storage_root, ree_id).write_manifest(manifest)


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


def _workspace_file_entries(storage_root: Path, ree_id: str) -> list[dict[str, Any]]:
    store = _store(storage_root, ree_id)
    root = store.layout.workspace
    return [
        {
            "path": (rel := fp.relative_to(root).as_posix()),
            "kind": classify_file_kind(rel),
            "size": fp.stat().st_size,
        }
        for fp in _iter_workspace_files(store)
    ]


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


def _workspace_ree_files_with_content(
    storage_root: Path, ree_id: str
) -> list[dict[str, Any]]:
    """Enumerate top-level files in the REE root (manifest, snapshot, etc.)."""
    layout = _layout(storage_root, ree_id)
    ree_root = layout.root
    if not ree_root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    ree_files: list[dict[str, Any]] = []
    for fp in sorted(ree_root.iterdir(), key=lambda p: p.name):
        if not fp.is_file():
            continue
        if is_metadata_file_name(fp.name):
            continue
        rel = fp.relative_to(ree_root).as_posix()
        size = fp.stat().st_size
        content = (
            _read_text_if_possible(fp)
            if should_inline_file_content(rel, size)
            else None
        )
        tag = "REE"
        if rel == "manifest.json":
            tag = "Manifest"
        elif rel.endswith(".zip") or rel.endswith(".tar.gz"):
            tag = "Archive"
        ree_files.append(
            {"path": rel, "kind": "ree", "tag": tag, "size": size, "content": content}
        )
    return ree_files


def _clear_workspace_content(store: ReeStore) -> None:
    """Clear upstream, overlay, workspace, and the snapshot archive."""
    if not store.layout.root.exists():
        raise FileNotFoundError(f"REE {store.layout.root.name} not found")
    store.upstream.clear()
    store.upstream.ensure_root()
    store.overlay.clear()
    store.overlay.ensure_root()
    store.workspace.clear()
    store.workspace.ensure_root()
    snapshot = store.layout.snapshot_archive
    if snapshot.exists():
        snapshot.unlink()


def _save_snapshot_archive(store: ReeStore, source_path: Path) -> str:
    """Pack source_path into snapshot.tar.gz and return the archive filename."""
    pack_directory_tar_gz(source_path, store.layout.snapshot_archive)
    return store.layout.snapshot_archive.name  # always "snapshot.tar.gz"


def _validate_draft_patch(ree_patch: dict[str, Any]) -> None:
    unsupported = sorted(set(ree_patch) - _DRAFT_PATCH_FIELDS)
    if unsupported:
        raise ValueError(
            "REE draft patch contains backend-managed fields: " + ", ".join(unsupported)
        )


def _patch_workspace_ree(
    storage_root: Path,
    ree_id: str,
    metadata: dict[str, Any],
    ree_patch: dict[str, Any],
) -> dict[str, Any]:
    ree = _ree_from_metadata(metadata).apply_patch(ree_patch)
    metadata["reeDraft"] = ree.model_dump(exclude_none=True)
    if ree.name:
        metadata["name"] = ree.name
    if ree.origin_url:
        metadata["externalRef"] = ree.origin_url
    source = metadata.get("source")
    if isinstance(source, dict) and ree.source_type:
        source["sourceType"] = ree.source_type
        metadata["source"] = source
    return get_workspace(
        storage_root,
        ree_id,
        seed_metadata=_write_metadata(storage_root, ree_id, metadata),
    )


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------


def workspace_dir(storage_root: Path, ree_id: str) -> Path:
    """Return the path to the materialized workspace/ directory."""
    return _layout(storage_root, ree_id).workspace


def artifact_dir(storage_root: Path, ree_id: str) -> Path:
    """Return the path to the artifacts/ directory."""
    return _layout(storage_root, ree_id).artifacts


def metadata_path(storage_root: Path, ree_id: str) -> Path:
    return _layout(storage_root, ree_id).metadata


def ree_manifest_path(storage_root: Path, ree_id: str) -> Path:
    return _layout(storage_root, ree_id).manifest


def workspace_exists(storage_root: Path, ree_id: str) -> bool:
    return metadata_path(storage_root, ree_id).exists()


def read_workspace_metadata(storage_root: Path, ree_id: str) -> dict[str, Any]:
    return _read_metadata(storage_root, ree_id)


def list_workspace_metadata(
    storage_root: Path, status: str | None = None
) -> list[dict[str, Any]]:
    storage_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for entry in sorted(storage_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        meta_file = entry / ".workspace.json"
        if not meta_file.exists():
            continue
        try:
            metadata: dict[str, Any] = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if status and metadata.get("status") != status:
            continue
        records.append(metadata)
    records.sort(key=lambda m: m.get("updatedAt", ""), reverse=True)
    return records


def get_workspace(
    storage_root: Path,
    ree_id: str,
    seed_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = seed_metadata or _read_metadata(storage_root, ree_id)
    _sync_downloadable_files(storage_root, ree_id, metadata)
    detail = dict(metadata)
    detail["files"] = _workspace_files_with_content(storage_root, ree_id)
    detail["reeFiles"] = _workspace_ree_files_with_content(storage_root, ree_id)
    return detail


def list_files(storage_root: Path, ree_id: str) -> list[dict[str, Any]]:
    return _workspace_file_entries(storage_root, ree_id)


def create_workspace(
    storage_root: Path,
    source_mode: str,
    origin_url: str | None = None,
    source_type: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    storage_root.mkdir(parents=True, exist_ok=True)
    ree_id = uuid.uuid4().hex
    store = _store(storage_root, ree_id)
    store.ensure_dirs()

    metadata = _default_metadata(ree_id, name)

    if source_mode == "url":
        if not origin_url or not source_type:
            raise ValueError(
                "origin_url and source_type are required when source_mode is 'url'"
            )
        metadata["externalRef"] = origin_url
        metadata["reeDraft"] = REE.model_validate(
            {
                "name": str(name or metadata["name"]),
                "origin_url": origin_url,
                "source_type": source_type,
            }
        ).model_dump(exclude_none=True)
        _write_metadata(storage_root, ree_id, metadata)
        acquire_source(storage_root, ree_id, origin_url, source_type)
        return get_workspace(storage_root, ree_id)

    if source_mode == "demo":
        (store.layout.workspace / "README.md").write_text(
            "# Demo workspace\n\nThis workspace was initialized in demo mode.\n",
            encoding="utf-8",
        )
        metadata["status"] = "ready"
        metadata["source"] = {"mode": "demo", "acquiredAt": _utc_now()}

    return get_workspace(
        storage_root,
        ree_id,
        seed_metadata=_write_metadata(storage_root, ree_id, metadata),
    )


def patch_ree_draft(
    storage_root: Path, ree_id: str, ree_patch: dict[str, Any]
) -> dict[str, Any]:
    _validate_draft_patch(ree_patch)
    metadata = _read_metadata(storage_root, ree_id)
    return _patch_workspace_ree(storage_root, ree_id, metadata, ree_patch)


def patch_workspace(
    storage_root: Path, ree_id: str, ree_patch: dict[str, Any]
) -> dict[str, Any]:
    metadata = _read_metadata(storage_root, ree_id)
    return _patch_workspace_ree(storage_root, ree_id, metadata, ree_patch)


def delete_workspace(storage_root: Path, ree_id: str) -> None:
    root = _layout(storage_root, ree_id).root
    if not root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    shutil.rmtree(root)


def read_file_content(storage_root: Path, ree_id: str, path: str) -> dict[str, Any]:
    normalized = _validate_user_path(path)
    fp = _layout(storage_root, ree_id).workspace_file(normalized)
    if not fp.exists() or not fp.is_file():
        raise FileNotFoundError(path)
    return {"content": fp.read_text(encoding="utf-8"), "updatedAt": _utc_now()}


def read_file_bytes(storage_root: Path, ree_id: str, path: str) -> bytes:
    normalized = _validate_user_path(path)
    fp = _layout(storage_root, ree_id).workspace_file(normalized)
    if not fp.exists() or not fp.is_file():
        raise FileNotFoundError(path)
    return fp.read_bytes()


def write_file_content(
    storage_root: Path, ree_id: str, path: str, content: str
) -> dict[str, Any]:
    normalized = _validate_user_path(path)
    store = _store(storage_root, ree_id)
    # Write to overlay (source of truth for user edits) and mirror to workspace.
    store.overlay.write_text(normalized, content)
    store.workspace.write_text(normalized, content)
    _write_metadata(storage_root, ree_id, _read_metadata(storage_root, ree_id))
    return {"etag": None, "updatedAt": _utc_now()}


def delete_file_content(storage_root: Path, ree_id: str, path: str) -> dict[str, Any]:
    normalized = _validate_user_path(path)
    store = _store(storage_root, ree_id)
    if not store.workspace.is_file(normalized):
        raise FileNotFoundError(path)
    store.overlay.delete_if_exists(normalized)
    # Restore from upstream if the file originated there; otherwise remove.
    if store.upstream.is_file(normalized):
        store.workspace.write_bytes(normalized, store.upstream.read_bytes(normalized))
    else:
        store.workspace.delete_if_exists(normalized)
    _write_metadata(storage_root, ree_id, _read_metadata(storage_root, ree_id))
    return {"deletedAt": _utc_now()}


def acquire_source(
    storage_root: Path,
    ree_id: str,
    origin_url: str,
    source_type: str,
) -> dict[str, Any]:
    store = _store(storage_root, ree_id)
    if not store.layout.root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    _clear_workspace_content(store)

    metadata = _read_metadata(storage_root, ree_id)
    metadata["externalRef"] = origin_url
    metadata["source"] = {
        "mode": "download",
        "originUrl": origin_url,
        "sourceType": source_type,
        "acquiredAt": _utc_now(),
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        acquired: Path
        if source_type == "git":
            clone_dir = tmp / "repo"
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", origin_url, str(clone_dir)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise RuntimeError("git is required to acquire git sources") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(exc.stderr.strip() or "git clone failed") from exc
            copy_tree_contents(clone_dir, store.layout.upstream)
            acquired = clone_dir
        else:
            archive_name = safe_filename(
                Path(urlparse(origin_url).path).name, "source.archive"
            )
            archive_path = tmp / archive_name
            extract_dir = tmp / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            download_or_copy(origin_url, archive_path)
            if source_type == "zip" or archive_path.suffix.lower() == ".zip":
                safe_extract_zip(archive_path, extract_dir)
            else:
                safe_extract_tar(archive_path, extract_dir)
            copy_tree_contents(extract_dir, store.layout.upstream)
            acquired = extract_dir

        snapshot_archive = _save_snapshot_archive(store, acquired)

    _materialize_workspace(store)

    metadata["source"]["snapshotArchive"] = snapshot_archive
    metadata["source"]["snapshotCapturedAt"] = _utc_now()
    metadata["status"] = "ready"
    ree = _ree_from_metadata(metadata).model_copy(
        update={"origin_url": origin_url, "source_type": source_type}
    )
    metadata["reeDraft"] = ree.with_source(metadata.get("source")).model_dump(
        exclude_none=True
    )
    return get_workspace(
        storage_root,
        ree_id,
        seed_metadata=_write_metadata(storage_root, ree_id, metadata),
    )


def init_source_upload(
    storage_root: Path,
    ree_id: str,
    file_name: str,
    size: int,
    content_type: str,
) -> dict[str, Any]:
    _ = file_name, size, content_type  # accepted for API symmetry
    if not _layout(storage_root, ree_id).root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    token = uuid.uuid4().hex
    return {
        "uploadToken": token,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def store_source_upload_bytes(
    storage_root: Path, ree_id: str, token: str, data: bytes
) -> dict[str, Any]:
    layout = _layout(storage_root, ree_id)
    if not layout.root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    stage_path = layout.upload_staging_file(token)
    stage_path.write_bytes(data)
    return {"uploadToken": token, "storedAt": _utc_now()}


def complete_source_upload(
    storage_root: Path,
    ree_id: str,
    upload_token: str,
    archive_name: str,
) -> dict[str, Any]:
    store = _store(storage_root, ree_id)
    if not store.layout.workspace.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    staged = store.layout.upload_staging_file(upload_token)
    staged_bytes = staged.read_bytes() if staged.exists() else b""
    _clear_workspace_content(store)

    if staged_bytes:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(staged_bytes)
            tmp_path = Path(tmp.name)
        try:
            with tempfile.TemporaryDirectory() as extract_dir:
                extracted = Path(extract_dir)
                if archive_name.lower().endswith(".zip"):
                    safe_extract_zip(tmp_path, extracted)
                else:
                    safe_extract_tar(tmp_path, extracted)
                copy_tree_contents(extracted, store.layout.upstream)
                snapshot_archive = _save_snapshot_archive(store, extracted)
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        readme = store.layout.upstream / "README.md"
        readme.write_text(
            f"# {archive_name}\n\nArchive upload completed without bytes.\n",
            encoding="utf-8",
        )
        snapshot_archive = _save_snapshot_archive(store, store.layout.upstream)

    _materialize_workspace(store)
    staged.unlink(missing_ok=True)

    snapshot_captured_at = _utc_now()
    metadata = _read_metadata(storage_root, ree_id)
    metadata["status"] = "ready"
    metadata["source"] = {
        "mode": "upload",
        "archiveName": archive_name,
        "snapshotArchive": snapshot_archive,
        "snapshotCapturedAt": snapshot_captured_at,
        "uploadToken": upload_token,
        "completedAt": snapshot_captured_at,
    }
    metadata["reeDraft"] = (
        _ree_from_metadata(metadata)
        .with_source(metadata["source"])
        .model_dump(exclude_none=True)
    )
    return {
        "sourceSnapshotId": upload_token,
        "status": "ready",
        "workspace": get_workspace(
            storage_root,
            ree_id,
            seed_metadata=_write_metadata(storage_root, ree_id, metadata),
        ),
    }


def remove_source(storage_root: Path, ree_id: str) -> dict[str, Any]:
    store = _store(storage_root, ree_id)
    _clear_workspace_content(store)
    metadata = _read_metadata(storage_root, ree_id)
    metadata["status"] = "draft"
    metadata["externalRef"] = None
    metadata["source"] = None
    cleared_ree = (
        _ree_from_metadata(metadata)
        .with_source(None)
        .model_copy(
            update={
                "origin_url": "",
                "source_type": "",
                "runtime": "",
                "build_runtime_script": "",
                "activation_script": "",
                "sbom": "",
                "source_included": False,
                "runtime_included": False,
                "dependency_level": 0,
                "environment_level": 0,
                "machine_level": 0,
                "detected_dependencies": None,
            }
        )
    )
    report_path = _layout(storage_root, ree_id).artifact_file(
        "reproducibility-report.json"
    )
    if report_path.exists():
        report_path.unlink()
    metadata["reeDraft"] = cleared_ree.model_dump(exclude_none=True)
    return {
        "invalidatedSteps": ["source", "evaluate", "workflow"],
        "workspace": get_workspace(
            storage_root,
            ree_id,
            seed_metadata=_write_metadata(storage_root, ree_id, metadata),
        ),
    }


def build_workspace_ree_archive(storage_root: Path, ree_id: str) -> bytes:
    metadata = _read_metadata(storage_root, ree_id)
    layout = _layout(storage_root, ree_id)
    ree = _ree_from_metadata(metadata)
    sidecar_manifest = _build_manifest_payload(metadata, ree, ree_id=ree_id)

    artifact_plan = _build_artifact_plan(layout, ree)
    include_snapshot = should_include_snapshot(
        source_included=bool(sidecar_manifest.get("source_included")),
        source_snapshot_archive=sidecar_manifest.get("source_snapshot_archive"),
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
    ree_draft = dict(metadata.get("reeDraft") or {})
    ree_draft["downloadable_files"] = [path for path, _ in entries]
    metadata["reeDraft"] = ree_draft
    store = _store(storage_root, ree_id)
    store.write_metadata_json(metadata)
    archive_bytes = build_zip_bytes(entries)
    store.write_manifest(sidecar_manifest)
    return archive_bytes
