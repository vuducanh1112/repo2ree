from __future__ import annotations

import json
import shutil
import tarfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel

from repo2ree_api.settings import service_settings
from repo2ree_api.metadata.ree import REE


class ReviewUploadInitPayload(BaseModel):
    fileName: str
    size: int
    contentType: str


class ReviewUploadCompletePayload(BaseModel):
    uploadToken: str
    archiveName: str


def review_root() -> Path:
    return service_settings.REVIEWS_STORAGE_DIR


def ensure_review_root() -> None:
    review_root().mkdir(parents=True, exist_ok=True)


def review_dir(review_id: str) -> Path:
    return review_root() / review_id


def review_workspace_dir(review_id: str) -> Path:
    return review_dir(review_id) / "workspace"


def review_metadata_path(review_id: str) -> Path:
    return review_dir(review_id) / ".review.json"


def _upload_stage_path(review_id: str, token: str) -> Path:
    return review_dir(review_id) / f".upload.{token}.bin"


def _review_archive_path(review_id: str, archive_name: str) -> Path:
    safe_name = (archive_name or "review.zip").strip().replace("\\", "/").split("/")[-1]
    safe_name = safe_name or "review.zip"
    return review_dir(review_id) / safe_name


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_review_metadata(review_id: str) -> dict[str, Any]:
    path = review_metadata_path(review_id)
    if not path.exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    return _json_load(path)


def _write_review_metadata(review_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    metadata["updatedAt"] = _utc_now()
    _json_dump(review_metadata_path(review_id), metadata)
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
        "reeDraft": REE(name=default_name).model_dump(by_alias=True, exclude_none=True),
    }


def _clear_review_workspace(review_id: str) -> None:
    root = review_workspace_dir(review_id)
    if not root.exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)


def _clear_review_root_content(review_id: str) -> None:
    root = review_dir(review_id)
    if not root.exists():
        raise FileNotFoundError(f"Review {review_id} not found")

    for item in root.iterdir():
        if item.name in {"workspace", ".review.json"}:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink(missing_ok=True)

    workspace = review_workspace_dir(review_id)
    workspace.mkdir(parents=True, exist_ok=True)
    _clear_review_workspace(review_id)


def _is_symlink_entry(member: zipfile.ZipInfo) -> bool:
    mode = (member.external_attr >> 16) & 0o170000
    return mode == 0o120000


def _validate_zip_member(member: zipfile.ZipInfo) -> None:
    member_path = PurePosixPath(member.filename)
    if member_path.is_absolute():
        raise ValueError("Invalid archive entry path")
    if any(part in {"", ".", ".."} for part in member_path.parts):
        raise ValueError("Invalid archive entry path")
    if _is_symlink_entry(member):
        raise ValueError("Archive symlink entries are not supported")


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            _validate_zip_member(member)
            candidate = (destination / member.filename).resolve()
            try:
                candidate.relative_to(destination_root)
            except ValueError as exc:
                raise ValueError("Invalid archive entry path") from exc

            candidate.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as src, candidate.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    member_path = PurePosixPath(member.name)
    if member_path.is_absolute():
        raise ValueError("Invalid archive entry path")
    if any(part in {"", ".", ".."} for part in member_path.parts):
        raise ValueError("Invalid archive entry path")
    if member.issym() or member.islnk():
        raise ValueError("Archive symlink entries are not supported")


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with tarfile.open(archive_path, mode="r:*") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            _validate_tar_member(member)
            candidate = (destination / member.name).resolve()
            try:
                candidate.relative_to(destination_root)
            except ValueError as exc:
                raise ValueError("Invalid archive entry path") from exc

            file_obj = archive.extractfile(member)
            if file_obj is None:
                continue
            candidate.parent.mkdir(parents=True, exist_ok=True)
            with file_obj, candidate.open("wb") as dst:
                shutil.copyfileobj(file_obj, dst)


def _resolve_snapshot_archive_path(search_root: Path, snapshot_ref: str) -> Path | None:
    normalized = (snapshot_ref or "").strip().replace("\\", "/")
    if not normalized:
        return None
    normalized = normalized.lstrip("/")
    normalized_path = PurePosixPath(normalized)
    if normalized_path.is_absolute() or any(
        part in {"", ".", ".."} for part in normalized_path.parts
    ):
        raise ValueError("Invalid archive entry path")

    candidate_strings = [normalized]
    basename = normalized_path.name
    if basename and normalized != basename:
        candidate_strings.append(basename)
    if basename:
        candidate_strings.append(f"ree/{basename}")

    seen: set[str] = set()
    search_root_resolved = search_root.resolve()
    for candidate_str in candidate_strings:
        if candidate_str in seen:
            continue
        seen.add(candidate_str)
        candidate = (search_root / candidate_str).resolve()
        try:
            candidate.relative_to(search_root_resolved)
        except ValueError as exc:
            raise ValueError("Invalid archive entry path") from exc
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _extract_included_source_snapshot(
    snapshot_search_root: Path,
    destination_root: Path,
    ree_draft: dict[str, Any],
) -> None:
    if not bool(ree_draft.get("_sourceIncluded")):
        return

    snapshot_ref = str(ree_draft.get("_sourceSnapshotArchive") or "").strip()
    if not snapshot_ref:
        return

    snapshot_archive_path = _resolve_snapshot_archive_path(
        snapshot_search_root, snapshot_ref
    )
    if snapshot_archive_path is None:
        return

    destination_root.mkdir(parents=True, exist_ok=True)

    lower_name = snapshot_archive_path.name.lower()
    if lower_name.endswith(".zip"):
        _safe_extract_zip(snapshot_archive_path, destination_root)
    else:
        _safe_extract_tar(snapshot_archive_path, destination_root)


def _manifest_to_ree_draft(
    manifest: dict[str, Any], uploaded_archive: str
) -> dict[str, Any]:
    payload = {
        "name": manifest.get("name") or "",
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
        "_evalLevel": manifest.get("eval_level") or 0,
        "_sealedAt": manifest.get("sealed_at"),
        "_sealHash": manifest.get("seal_hash"),
        "_sourceIncluded": bool(manifest.get("source_included", False)),
        "_sourceAvailable": bool(manifest.get("source_available", False)),
        "_sourceAcquiredBy": manifest.get("source_acquired_by") or "",
        "_sourceSnapshotArchive": manifest.get("source_snapshot_archive"),
        "_sourceSnapshotCapturedAt": manifest.get("source_snapshot_captured_at"),
        "_runtimeIncluded": bool(manifest.get("runtime_included", False)),
        "_downloadableFiles": manifest.get("downloadable_files") or [],
        "_uploadedArchive": uploaded_archive,
    }
    ree = REE.model_validate(payload)
    return ree.model_dump(by_alias=True, exclude_none=True)


def _list_files_under(
    root: Path, *, include_hidden: bool = True
) -> list[dict[str, Any]]:
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {root}")

    entries: list[dict[str, Any]] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        rel_path_obj = file_path.relative_to(root)
        if not include_hidden and any(
            part.startswith(".") for part in rel_path_obj.parts
        ):
            continue
        rel_path = rel_path_obj.as_posix()
        entries.append({"path": rel_path, "size": file_path.stat().st_size})
    return entries


def get_review(review_id: str) -> dict[str, Any]:
    metadata = _read_review_metadata(review_id)
    if metadata.get("status") == "ready":
        _extract_included_source_snapshot(
            review_dir(review_id),
            review_workspace_dir(review_id),
            dict(metadata.get("reeDraft") or {}),
        )
    detail = dict(metadata)
    detail["files"] = _list_files_under(review_dir(review_id))
    detail["workspaceFiles"] = _list_files_under(review_workspace_dir(review_id))
    return detail


def init_review_upload(payload: ReviewUploadInitPayload) -> dict[str, Any]:
    ensure_review_root()
    review_id = uuid.uuid4().hex
    root = review_dir(review_id)
    root.mkdir(parents=True, exist_ok=True)
    review_workspace_dir(review_id).mkdir(parents=True, exist_ok=True)

    metadata = _default_review_metadata(review_id, payload.fileName)
    _write_review_metadata(review_id, metadata)

    token = uuid.uuid4().hex
    return {
        "reviewId": review_id,
        "uploadUrl": f"/api/v1/reviews/{review_id}/upload/{token}",
        "uploadToken": token,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def store_review_upload_bytes(
    review_id: str, token: str, data: bytes
) -> dict[str, Any]:
    if not review_dir(review_id).exists():
        raise FileNotFoundError(f"Review {review_id} not found")
    stage_path = _upload_stage_path(review_id, token)
    stage_path.write_bytes(data)
    return {"uploadToken": token, "storedAt": _utc_now()}


def complete_review_upload(
    review_id: str, payload: ReviewUploadCompletePayload
) -> dict[str, Any]:
    metadata = _read_review_metadata(review_id)
    if not str(payload.archiveName or "").lower().endswith(".zip"):
        raise ValueError("Review upload requires a .zip archive")
    staged_archive = _upload_stage_path(review_id, payload.uploadToken)
    if not staged_archive.exists() or staged_archive.stat().st_size == 0:
        raise ValueError("Upload content is empty")

    staged_bytes = staged_archive.read_bytes()
    _clear_review_root_content(review_id)

    archive_path = _review_archive_path(review_id, payload.archiveName)
    archive_path.write_bytes(staged_bytes)

    try:
        _safe_extract_zip(archive_path, review_dir(review_id))
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded file is not a valid zip archive") from exc
    finally:
        staged_archive.unlink(missing_ok=True)

    manifest_path = review_dir(review_id) / "ree" / "ree.json"
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ValueError("Archive must contain ree/ree.json")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON in ree/ree.json") from exc

    metadata["status"] = "ready"
    metadata["name"] = str(manifest.get("name") or metadata.get("name") or "review")
    metadata["archiveName"] = payload.archiveName
    metadata["reeDraft"] = _manifest_to_ree_draft(manifest, payload.archiveName)
    _extract_included_source_snapshot(
        review_dir(review_id),
        review_workspace_dir(review_id),
        dict(metadata.get("reeDraft") or {}),
    )
    _write_review_metadata(review_id, metadata)

    return {
        "status": "ready",
        "review": get_review(review_id),
    }
