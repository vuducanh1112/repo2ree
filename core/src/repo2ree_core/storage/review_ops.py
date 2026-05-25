"""Review upload and lifecycle operations.

Imperative shell for the review workflow. All functions take
``storage_root: Path`` explicitly; no application settings are imported.

Review on-disk layout under ``<storage_root>/<review_id>/``:
  .review.json        review metadata
  workspace/          workspace directory (extracted source or empty)
  upload-staging/     in-flight upload bytes
  <archive>.zip       the uploaded REE bundle
  ree/ree.json        manifest extracted from the bundle
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.domain.ree import REE
from repo2ree_core.storage.extract import safe_extract_tar, safe_extract_zip


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _review_dir(storage_root: Path, review_id: str) -> Path:
    return storage_root / review_id


def _review_workspace_dir(storage_root: Path, review_id: str) -> Path:
    return _review_dir(storage_root, review_id) / "workspace"


def _review_metadata_path(storage_root: Path, review_id: str) -> Path:
    return _review_dir(storage_root, review_id) / ".review.json"


def _upload_stage_path(storage_root: Path, review_id: str, token: str) -> Path:
    return _review_dir(storage_root, review_id) / "upload-staging" / f"{token}.bin"


def _review_archive_path(storage_root: Path, review_id: str, archive_name: str) -> Path:
    safe_name = (archive_name or "review.zip").strip().replace("\\", "/").split("/")[-1]
    safe_name = safe_name or "review.zip"
    return _review_dir(storage_root, review_id) / safe_name


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_review_metadata(storage_root: Path, review_id: str) -> dict[str, Any]:
    path = _review_metadata_path(storage_root, review_id)
    if not path.exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_review_metadata(
    storage_root: Path, review_id: str, metadata: dict[str, Any]
) -> dict[str, Any]:
    metadata["updatedAt"] = _utc_now()
    path = _review_metadata_path(storage_root, review_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return metadata


def _default_review_metadata(
    review_id: str, file_name: str | None = None
) -> dict[str, Any]:
    ts = _utc_now()
    default_name = (file_name or "review").strip() or "review"
    return {
        "reviewId": review_id,
        "name": default_name,
        "status": "uploading",
        "createdAt": ts,
        "updatedAt": ts,
        "reeDraft": REE(name=default_name).model_dump(exclude_none=True),
    }


def _clear_review_root_content(storage_root: Path, review_id: str) -> None:
    root = _review_dir(storage_root, review_id)
    if not root.exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    preserved = {".review.json", "workspace", "upload-staging"}
    for item in root.iterdir():
        if item.name in preserved:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink(missing_ok=True)
    workspace = _review_workspace_dir(storage_root, review_id)
    workspace.mkdir(parents=True, exist_ok=True)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)


def _resolve_snapshot_archive(search_root: Path, snapshot_ref: str) -> Path | None:
    """Locate a snapshot archive within search_root, trying several candidate paths."""
    normalized = (snapshot_ref or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    norm_path = PurePosixPath(normalized)
    if norm_path.is_absolute() or any(
        part in {"", ".", ".."} for part in norm_path.parts
    ):
        raise ValueError("Invalid archive entry path")

    candidates = [normalized]
    basename = norm_path.name
    if basename and normalized != basename:
        candidates.append(basename)
    if basename:
        candidates.append(f"ree/{basename}")

    seen: set[str] = set()
    root_resolved = search_root.resolve()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        fp = (search_root / cand).resolve()
        try:
            fp.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError("Invalid archive entry path") from exc
        if fp.exists() and fp.is_file():
            return fp
    return None


def _extract_included_source_snapshot(
    snapshot_search_root: Path,
    destination_root: Path,
    ree_draft: dict[str, Any],
) -> None:
    if not bool(ree_draft.get("source_included")):
        return
    snapshot_ref = str(ree_draft.get("source_snapshot_archive") or "").strip()
    if not snapshot_ref:
        return
    archive = _resolve_snapshot_archive(snapshot_search_root, snapshot_ref)
    if archive is None:
        return
    destination_root.mkdir(parents=True, exist_ok=True)
    if archive.name.lower().endswith(".zip"):
        safe_extract_zip(archive, destination_root)
    else:
        safe_extract_tar(archive, destination_root)


def _manifest_to_ree_draft(
    manifest: dict[str, Any], uploaded_archive: str
) -> dict[str, Any]:
    payload = {
        "name": manifest.get("name") or "",
        "catalog_metadata": manifest.get("catalog_metadata") or {},
        "origin_url": manifest.get("origin_url") or "",
        "source_type": manifest.get("source_type") or "",
        "runtime": manifest.get("runtime") or "",
        "build_runtime_script": manifest.get("build_script") or "",
        "activation_script": manifest.get("activation_script") or "",
        "sbom": manifest.get("sbom") or "",
        "swhid": manifest.get("swhid") or "",
        "zenodo_doi": manifest.get("zenodo_doi"),
        "dataverse_doi": manifest.get("dataverse_doi"),
        "hardware_description": manifest.get("hardware_description") or {},
        "dependency_level": manifest.get("dependency_level") or 0,
        "environment_level": manifest.get("environment_level") or 0,
        "machine_level": manifest.get("machine_level") or 0,
        "sealed_at": manifest.get("sealed_at"),
        "seal_hash": manifest.get("seal_hash"),
        "source_included": bool(manifest.get("source_included", False)),
        "source_available": bool(manifest.get("source_available", False)),
        "source_acquired_by": manifest.get("source_acquired_by") or "",
        "source_snapshot_archive": manifest.get("source_snapshot_archive"),
        "source_snapshot_captured_at": manifest.get("source_snapshot_captured_at"),
        "runtime_included": bool(manifest.get("runtime_included", False)),
        "downloadable_files": manifest.get("downloadable_files") or [],
        "uploaded_archive": uploaded_archive,
    }
    return REE.model_validate(payload).model_dump(exclude_none=True)


def _list_files_under(
    root: Path, *, include_hidden: bool = True
) -> list[dict[str, Any]]:
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")
    entries: list[dict[str, Any]] = []
    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(root)
        if not include_hidden and any(part.startswith(".") for part in rel.parts):
            continue
        entries.append({"path": rel.as_posix(), "size": fp.stat().st_size})
    return entries


# ---------------------------------------------------------------------------
# Public API — path accessors
# ---------------------------------------------------------------------------


def review_dir(storage_root: Path, review_id: str) -> Path:
    return _review_dir(storage_root, review_id)


def review_workspace_dir(storage_root: Path, review_id: str) -> Path:
    return _review_workspace_dir(storage_root, review_id)


def review_metadata_path(storage_root: Path, review_id: str) -> Path:
    return _review_metadata_path(storage_root, review_id)


# ---------------------------------------------------------------------------
# Public API — operations
# ---------------------------------------------------------------------------


def get_review(storage_root: Path, review_id: str) -> dict[str, Any]:
    metadata = _read_review_metadata(storage_root, review_id)
    if metadata.get("status") == "ready":
        _extract_included_source_snapshot(
            _review_dir(storage_root, review_id),
            _review_workspace_dir(storage_root, review_id),
            dict(metadata.get("reeDraft") or {}),
        )
    detail = dict(metadata)
    detail["files"] = _list_files_under(_review_dir(storage_root, review_id))
    detail["workspaceFiles"] = _list_files_under(
        _review_workspace_dir(storage_root, review_id)
    )
    return detail


def init_review_upload(
    storage_root: Path,
    file_name: str,
    size: int,
    content_type: str,
) -> dict[str, Any]:
    _ = size, content_type  # accepted for API symmetry
    storage_root.mkdir(parents=True, exist_ok=True)
    review_id = uuid.uuid4().hex
    root = _review_dir(storage_root, review_id)
    root.mkdir(parents=True, exist_ok=True)
    _review_workspace_dir(storage_root, review_id).mkdir(parents=True, exist_ok=True)
    (root / "upload-staging").mkdir(parents=True, exist_ok=True)

    metadata = _default_review_metadata(review_id, file_name)
    _write_review_metadata(storage_root, review_id, metadata)

    token = uuid.uuid4().hex
    return {
        "reviewId": review_id,
        "uploadToken": token,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def store_review_upload_bytes(
    storage_root: Path, review_id: str, token: str, data: bytes
) -> dict[str, Any]:
    if not _review_dir(storage_root, review_id).exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    stage_path = _upload_stage_path(storage_root, review_id, token)
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    stage_path.write_bytes(data)
    return {"uploadToken": token, "storedAt": _utc_now()}


def complete_review_upload(
    storage_root: Path,
    review_id: str,
    upload_token: str,
    archive_name: str,
) -> dict[str, Any]:
    import zipfile

    metadata = _read_review_metadata(storage_root, review_id)
    if not str(archive_name or "").lower().endswith(".zip"):
        raise ValueError("Review upload requires a .zip archive")
    staged = _upload_stage_path(storage_root, review_id, upload_token)
    if not staged.exists() or staged.stat().st_size == 0:
        raise ValueError("Upload content is empty")

    staged_bytes = staged.read_bytes()
    _clear_review_root_content(storage_root, review_id)

    archive_path = _review_archive_path(storage_root, review_id, archive_name)
    archive_path.write_bytes(staged_bytes)

    try:
        safe_extract_zip(archive_path, _review_dir(storage_root, review_id))
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded file is not a valid zip archive") from exc
    finally:
        staged.unlink(missing_ok=True)

    manifest_path = _review_dir(storage_root, review_id) / "ree" / "ree.json"
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ValueError("Archive must contain ree/ree.json")

    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON in ree/ree.json") from exc

    metadata["status"] = "ready"
    metadata["name"] = str(manifest.get("name") or metadata.get("name") or "review")
    metadata["archiveName"] = archive_name
    metadata["reeDraft"] = _manifest_to_ree_draft(manifest, archive_name)
    _extract_included_source_snapshot(
        _review_dir(storage_root, review_id),
        _review_workspace_dir(storage_root, review_id),
        dict(metadata.get("reeDraft") or {}),
    )
    _write_review_metadata(storage_root, review_id, metadata)

    return {"status": "ready", "review": get_review(storage_root, review_id)}
