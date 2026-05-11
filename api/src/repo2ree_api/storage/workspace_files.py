from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.request import urlopen

from pydantic import BaseModel, Field

from repo2ree_api.settings import service_settings
from repo2ree_core.domain.ree import REE


REE_ROOT_PREFIX = "ree/"
REE_MANIFEST_ENTRY_PATH = f"{REE_ROOT_PREFIX}ree.json"


class WorkspaceCreatePayload(BaseModel):
    sourceMode: Literal["url", "upload", "demo"]
    originUrl: str | None = None
    sourceType: Literal["git", "tarball", "zip"] | None = None
    name: str | None = None


class WorkspacePatchPayload(BaseModel):
    reePatch: dict[str, Any] = Field(default_factory=dict)
    expectedVersion: str | None = None


class SourceAcquirePayload(BaseModel):
    originUrl: str
    sourceType: Literal["git", "tarball", "zip"]


class UploadInitPayload(BaseModel):
    fileName: str
    size: int
    contentType: str


class SourceUploadCompletePayload(BaseModel):
    uploadToken: str
    archiveName: str


class WorkspaceFileContentPayload(BaseModel):
    path: str
    content: str
    ifMatch: str | None = None


def workspace_root() -> Path:
    return service_settings.WORKSPACE_STORAGE_DIR


def ensure_workspace_root() -> None:
    workspace_root().mkdir(parents=True, exist_ok=True)


def ree_dir(ree_id: str) -> Path:
    return workspace_root() / ree_id


def workspace_dir(ree_id: str) -> Path:
    return ree_dir(ree_id) / "workspace"


def metadata_path(ree_id: str) -> Path:
    return ree_dir(ree_id) / ".workspace.json"


def ree_manifest_path(ree_id: str) -> Path:
    return ree_dir(ree_id) / "manifest.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_filename(name: str | None, default: str) -> str:
    candidate = (name or default).strip().replace("\\", "/").split("/")[-1]
    return candidate or default


def _default_workspace_name(ree_id: str) -> str:
    return f"workspace-{ree_id[:8]}"


def _default_metadata(ree_id: str, name: str | None = None) -> dict[str, Any]:
    ts = _utc_now()
    workspace_name = name or _default_workspace_name(ree_id)
    return {
        "reeId": ree_id,
        "externalRef": None,
        "name": workspace_name,
        "status": "draft",
        "createdAt": ts,
        "updatedAt": ts,
        "reeDraft": REE(name=workspace_name).model_dump(
            by_alias=True, exclude_none=True
        ),
        "source": None,
    }


def _ree_from_metadata(metadata: dict[str, Any]) -> REE:
    return REE.from_metadata(metadata)


def _read_metadata(ree_id: str) -> dict[str, Any]:
    path = metadata_path(ree_id)
    if not path.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    return _json_load(path)


def _write_metadata(ree_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    _sync_downloadable_files_metadata(ree_id, metadata)
    _persist_manifest_sidecar(ree_id, metadata)
    metadata["updatedAt"] = _utc_now()
    _json_dump(metadata_path(ree_id), metadata)
    return metadata


def read_workspace_metadata(ree_id: str) -> dict[str, Any]:
    return _read_metadata(ree_id)


def workspace_exists(ree_id: str) -> bool:
    return metadata_path(ree_id).exists()


def _resolve_workspace_path(ree_id: str, path: str) -> Path:
    root = workspace_dir(ree_id).resolve()
    candidate = (workspace_dir(ree_id) / path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid workspace path") from exc
    if candidate.name.startswith(".workspace") or candidate.name.startswith(".upload."):
        raise ValueError("Invalid workspace path")
    return candidate


def _is_upload_staging(path: Path) -> bool:
    return path.name.startswith(".upload.")


def _is_metadata_file(path: Path) -> bool:
    return path.name == ".workspace.json"


def _iter_workspace_files(ree_id: str):
    root = workspace_dir(ree_id)
    if not root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if _is_metadata_file(file_path) or _is_upload_staging(file_path):
            continue
        yield file_path


def _relative_workspace_path(ree_id: str, path: Path) -> str:
    return path.relative_to(workspace_dir(ree_id)).as_posix()


def _file_kind(relative_path: str) -> str:
    if "/" not in relative_path and relative_path.lower().startswith("docker"):
        return "source"
    return "source"


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


_MAX_INLINE_TEXT_BYTES = 1024 * 1024
_MAX_INLINE_SBOM_BYTES = 8 * 1024 * 1024


def _should_inline_file_content(relative_path: str, size: int) -> bool:
    lower_path = relative_path.lower()
    if lower_path.endswith("sbom.json") and size > _MAX_INLINE_SBOM_BYTES:
        return False
    if size > _MAX_INLINE_TEXT_BYTES:
        return False
    return True


def list_workspace_metadata(status: str | None = None) -> list[dict[str, Any]]:
    ensure_workspace_root()
    records: list[dict[str, Any]] = []
    for entry in sorted(workspace_root().iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        meta_file = entry / ".workspace.json"
        if not meta_file.exists():
            continue
        metadata = _json_load(meta_file)
        if status and metadata.get("status") != status:
            continue
        records.append(metadata)
    records.sort(key=lambda item: item.get("updatedAt", ""), reverse=True)
    return records


def list_files(ree_id: str) -> list[dict[str, Any]]:
    return _workspace_file_entries(ree_id)


def _workspace_file_entries(ree_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for file_path in _iter_workspace_files(ree_id):
        relative_path = _relative_workspace_path(ree_id, file_path)
        entries.append(
            {
                "path": relative_path,
                "kind": _file_kind(relative_path),
                "size": file_path.stat().st_size,
            }
        )
    return entries


def _workspace_files_with_content(ree_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for file_path in _iter_workspace_files(ree_id):
        relative_path = _relative_workspace_path(ree_id, file_path)
        file_size = file_path.stat().st_size
        entries.append(
            {
                "path": relative_path,
                "kind": _file_kind(relative_path),
                "size": file_size,
                "content": _read_text_if_possible(file_path)
                if _should_inline_file_content(relative_path, file_size)
                else None,
            }
        )
    return entries


def _build_manifest_payload(
    ree_id: str,
    metadata: dict[str, Any],
    ree: REE,
) -> tuple[dict[str, Any], set[str]]:
    runtime_path = _normalize_workspace_path(ree.runtime)
    sbom_path = _normalize_workspace_path(ree.sbom)
    build_script_path = _normalize_workspace_path(ree.build_runtime_script)
    activation_script_path = _normalize_workspace_path(ree.activation_script)

    manifest = ree.as_manifest()
    manifest["name"] = (
        metadata.get("name") or manifest["name"] or f"workspace-{ree_id[:8]}"
    )
    manifest["origin_url"] = metadata.get("externalRef") or manifest["origin_url"]
    manifest["source_type"] = (
        (metadata.get("source") or {}).get("sourceType")
        if isinstance(metadata.get("source"), dict)
        else manifest["source_type"]
    )
    manifest["runtime"] = runtime_path or None
    manifest["build_script"] = build_script_path or None
    manifest["activation_script"] = activation_script_path or None
    manifest["sbom"] = sbom_path or None

    excluded_paths = {
        p
        for p in [runtime_path, sbom_path, build_script_path, activation_script_path]
        if p
    }
    return manifest, excluded_paths


def _build_ree_download_entries(
    ree_id: str,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ree = _ree_from_metadata(metadata)
    manifest, excluded_paths = _build_manifest_payload(ree_id, metadata, ree)

    entries: list[dict[str, Any]] = [
        {
            "path": REE_MANIFEST_ENTRY_PATH,
            "kind": "manifest",
            "tag": "Manifest",
            "workspacePath": None,
            "content": json.dumps(manifest, indent=2, sort_keys=True),
        }
    ]

    optional_entries = [
        {
            "workspace_path": manifest.get("runtime"),
            "archive_path": _archive_root_file_path(
                str(manifest.get("runtime") or ""), "runtime"
            ),
            "tag": "Runtime",
            "enabled": bool(manifest.get("runtime_included")),
        },
        {
            "workspace_path": manifest.get("sbom"),
            "archive_path": _archive_root_file_path(
                str(manifest.get("sbom") or ""), "sbom.json"
            ),
            "tag": "SBOM",
            "enabled": True,
        },
    ]

    for entry in optional_entries:
        workspace_path = entry["workspace_path"]
        archive_path = str(entry["archive_path"])
        tag = str(entry["tag"])
        enabled = bool(entry["enabled"])
        if not enabled:
            continue
        normalized = _normalize_workspace_path(str(workspace_path or ""))
        if not normalized or normalized not in excluded_paths:
            continue
        file_path = _resolve_workspace_path(ree_id, normalized)
        if not file_path.exists() or not file_path.is_file():
            continue
        entries.append(
            {
                "path": archive_path,
                "kind": "artifact",
                "tag": tag,
                "workspacePath": normalized,
                "content": None,
            }
        )

    if manifest["source_included"]:
        snapshot_archive_name = _normalize_workspace_path(
            str(manifest.get("source_snapshot_archive") or "")
        )
        if snapshot_archive_name:
            snapshot_archive_path = ree_dir(ree_id) / snapshot_archive_name
            if snapshot_archive_path.exists() and snapshot_archive_path.is_file():
                entries.append(
                    {
                        "path": (
                            f"{REE_ROOT_PREFIX}"
                            f"{_archive_workspace_path(snapshot_archive_name)}"
                        ),
                        "kind": "source",
                        "tag": "Source",
                        "workspacePath": None,
                        "reePath": snapshot_archive_name,
                        "content": None,
                    }
                )

    manifest["runtime_included"] = any(item["tag"] == "Runtime" for item in entries)
    return manifest, entries


def _sync_downloadable_files_metadata(ree_id: str, metadata: dict[str, Any]) -> None:
    _, entries = _build_ree_download_entries(ree_id, metadata)
    ree_draft = dict(metadata.get("reeDraft") or {})
    ree_draft["_downloadableFiles"] = [item["path"] for item in entries]
    metadata["reeDraft"] = ree_draft


def _persist_manifest_sidecar(ree_id: str, metadata: dict[str, Any]) -> None:
    manifest, _ = _build_manifest_payload(
        ree_id, metadata, _ree_from_metadata(metadata)
    )
    _json_dump(ree_manifest_path(ree_id), manifest)


def _strip_archive_suffix(name: str) -> str:
    lower = name.lower()
    for suffix in (".tar.gz", ".tgz", ".zip", ".tar", ".git"):
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def _snapshot_archive_name(seed: str | None, fallback: str = "source") -> str:
    base = _strip_archive_suffix(_safe_filename(seed, fallback)).strip()
    normalized = base or fallback
    return f"{normalized}-snapshot.tar.gz"


def _save_workspace_snapshot_archive(
    ree_id: str, source_path: Path, archive_name: str
) -> str:
    archive_file_name = _snapshot_archive_name(archive_name, "source")
    archive_path = ree_dir(ree_id) / archive_file_name
    with tarfile.open(archive_path, mode="w:gz") as tar:
        for item in sorted(source_path.iterdir(), key=lambda path: path.name):
            tar.add(item, arcname=item.name)
    return archive_file_name


def _workspace_ree_files_with_content(
    ree_id: str,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    _ = metadata
    ree_files: list[dict[str, Any]] = []
    ree_root = ree_dir(ree_id)
    if not ree_root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    for file_path in sorted(ree_root.iterdir(), key=lambda item: item.name):
        if not file_path.is_file():
            continue
        if _is_upload_staging(file_path) or _is_metadata_file(file_path):
            continue
        rel_path = file_path.relative_to(ree_root).as_posix()
        size = file_path.stat().st_size
        content = (
            _read_text_if_possible(file_path)
            if _should_inline_file_content(rel_path, size)
            else None
        )
        tag = "REE"
        if rel_path == "manifest.json":
            tag = "Manifest"
        elif rel_path.endswith(".zip"):
            tag = "Archive"
        ree_files.append(
            {
                "path": rel_path,
                "kind": "ree",
                "tag": tag,
                "size": size,
                "content": content,
            }
        )
    return ree_files


def get_workspace(
    ree_id: str, seed_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    metadata = seed_metadata or _read_metadata(ree_id)
    _sync_downloadable_files_metadata(ree_id, metadata)
    detail = dict(metadata)
    detail["files"] = _workspace_files_with_content(ree_id)
    detail["reeFiles"] = _workspace_ree_files_with_content(ree_id, metadata)
    return detail


def _clear_workspace_content(ree_id: str) -> None:
    root = workspace_dir(ree_id)
    if not root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    ree_root = ree_dir(ree_id)
    if ree_root.exists():
        for snapshot_archive in ree_root.glob("*-snapshot.tar.gz"):
            if snapshot_archive.is_file():
                snapshot_archive.unlink(missing_ok=True)


def create_workspace(payload: WorkspaceCreatePayload) -> dict[str, Any]:
    ensure_workspace_root()
    ree_id = uuid.uuid4().hex
    ree_root = ree_dir(ree_id)
    root = workspace_dir(ree_id)
    ree_root.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)

    metadata = _default_metadata(ree_id, payload.name)
    if payload.sourceMode == "url" and payload.originUrl and payload.sourceType:
        metadata["externalRef"] = payload.originUrl
        metadata["reeDraft"] = REE(
            name=str(payload.name or metadata["name"]),
            origin_url=payload.originUrl,
            source_type=payload.sourceType,
        ).model_dump(by_alias=True, exclude_none=True)
        metadata = _write_metadata(ree_id, metadata)
        acquire_source(
            ree_id,
            SourceAcquirePayload(
                originUrl=payload.originUrl, sourceType=payload.sourceType
            ),
        )
        return get_workspace(ree_id)

    if payload.sourceMode == "url":
        raise ValueError(
            "originUrl and sourceType are required when sourceMode is 'url'"
        )

    if payload.sourceMode == "demo":
        (root / "README.md").write_text(
            "# Demo workspace\n\nThis workspace was initialized in demo mode.\n",
            encoding="utf-8",
        )
        metadata["status"] = "ready"
        metadata["source"] = {"mode": "demo", "acquiredAt": _utc_now()}

    return get_workspace(ree_id, seed_metadata=_write_metadata(ree_id, metadata))


def patch_workspace(
    ree_id: str, patch_payload: WorkspacePatchPayload
) -> dict[str, Any]:
    metadata = _read_metadata(ree_id)
    ree_patch = dict(patch_payload.reePatch or {})
    ree = _ree_from_metadata(metadata).apply_patch(ree_patch)
    metadata["reeDraft"] = ree.model_dump(by_alias=True, exclude_none=True)

    if ree.name:
        metadata["name"] = ree.name
    if ree.origin_url:
        metadata["externalRef"] = ree.origin_url

    source = metadata.get("source")
    if isinstance(source, dict) and ree.source_type:
        source["sourceType"] = ree.source_type
        metadata["source"] = source

    return get_workspace(ree_id, seed_metadata=_write_metadata(ree_id, metadata))


def delete_workspace(ree_id: str) -> None:
    root = ree_dir(ree_id)
    if not root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    shutil.rmtree(root)


def read_file_content(ree_id: str, path: str) -> dict[str, Any]:
    file_path = _resolve_workspace_path(ree_id, path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(path)
    return {"content": file_path.read_text(encoding="utf-8"), "updatedAt": _utc_now()}


def read_file_bytes(ree_id: str, path: str) -> bytes:
    file_path = _resolve_workspace_path(ree_id, path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(path)
    return file_path.read_bytes()


def _normalize_workspace_path(path: str) -> str:
    return (path or "").lstrip("/").strip()


def _archive_workspace_path(path: str) -> str:
    return _normalize_workspace_path(path).replace("..", "_")


def _archive_root_file_path(path: str, fallback_name: str) -> str:
    normalized = _normalize_workspace_path(path)
    filename = _safe_filename(
        Path(normalized).name if normalized else None, fallback_name
    )
    return f"{REE_ROOT_PREFIX}{filename}"


def build_workspace_ree_archive(ree_id: str) -> bytes:
    metadata = _read_metadata(ree_id)
    manifest, entries = _build_ree_download_entries(ree_id, metadata)
    ree_draft = dict(metadata.get("reeDraft") or {})
    ree_draft["_downloadableFiles"] = [item["path"] for item in entries]
    metadata["reeDraft"] = ree_draft
    _json_dump(metadata_path(ree_id), metadata)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            archive_path = str(entry["path"])
            inline_content = entry.get("content")
            workspace_path = entry.get("workspacePath")
            ree_path = entry.get("reePath")
            if isinstance(inline_content, str):
                archive.writestr(archive_path, inline_content)
                continue
            if isinstance(ree_path, str) and ree_path:
                ree_file = (ree_dir(ree_id) / ree_path).resolve()
                if ree_file.exists() and ree_file.is_file():
                    archive.writestr(archive_path, ree_file.read_bytes())
                continue
            if not isinstance(workspace_path, str) or not workspace_path:
                continue
            source_file = _resolve_workspace_path(ree_id, workspace_path)
            if source_file.exists() and source_file.is_file():
                archive.writestr(archive_path, source_file.read_bytes())

    archive_bytes = buffer.getvalue()
    _json_dump(ree_manifest_path(ree_id), manifest)
    return archive_bytes


def write_file_content(ree_id: str, path: str, content: str) -> dict[str, Any]:
    file_path = _resolve_workspace_path(ree_id, path)
    _ensure_parent(file_path)
    file_path.write_text(content, encoding="utf-8")
    _write_metadata(ree_id, _read_metadata(ree_id))
    return {"etag": None, "updatedAt": _utc_now()}


def delete_file_content(ree_id: str, path: str) -> dict[str, Any]:
    file_path = _resolve_workspace_path(ree_id, path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(path)
    file_path.unlink()
    _write_metadata(ree_id, _read_metadata(ree_id))
    return {"deletedAt": _utc_now()}


def _download_or_open_local(origin_url: str, destination: Path) -> Path:
    parsed = urlparse(origin_url)
    if parsed.scheme in {"http", "https"}:
        with urlopen(origin_url) as response, destination.open("wb") as target:
            shutil.copyfileobj(response, target)
        return destination

    local_path = Path(origin_url)
    if local_path.exists():
        shutil.copy2(local_path, destination)
        return destination

    raise FileNotFoundError(f"Source not found: {origin_url}")


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    def _is_safe(member: tarfile.TarInfo) -> bool:
        member_path = destination / member.name
        try:
            member_path.resolve().relative_to(destination.resolve())
        except ValueError:
            return False
        return True

    with tarfile.open(archive, mode="r:*") as tar:
        safe_members = [member for member in tar.getmembers() if _is_safe(member)]
        tar.extractall(destination, members=safe_members)


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    dest_root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            extracted_path = (destination / member.filename).resolve()
            try:
                extracted_path.relative_to(dest_root)
            except ValueError:
                continue
            zf.extract(member, destination)


def _copy_tree_contents(source_path: Path, destination: Path) -> None:
    if source_path.is_dir():
        for item in source_path.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                _ensure_parent(target)
                shutil.copy2(item, target)
        return
    target = destination / source_path.name
    _ensure_parent(target)
    shutil.copy2(source_path, target)


def acquire_source(ree_id: str, payload: SourceAcquirePayload) -> dict[str, Any]:
    root = workspace_dir(ree_id)
    if not root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    _clear_workspace_content(ree_id)

    metadata = _read_metadata(ree_id)
    metadata["externalRef"] = payload.originUrl
    metadata["source"] = {
        "mode": "download",
        "originUrl": payload.originUrl,
        "sourceType": payload.sourceType,
        "acquiredAt": _utc_now(),
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        acquired_source_path: Path | None = None
        if payload.sourceType == "git":
            clone_dir = tmp_dir_path / "repo"
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", payload.originUrl, str(clone_dir)],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise RuntimeError("git is required to acquire git sources") from exc
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(exc.stderr.strip() or "git clone failed") from exc
            _copy_tree_contents(clone_dir, root)
            acquired_source_path = clone_dir
        else:
            archive_name = _safe_filename(
                Path(urlparse(payload.originUrl).path).name, "source.archive"
            )
            archive_path = tmp_dir_path / archive_name
            extract_dir = tmp_dir_path / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            _download_or_open_local(payload.originUrl, archive_path)
            if payload.sourceType == "zip" or archive_path.suffix.lower() == ".zip":
                _safe_extract_zip(archive_path, extract_dir)
            else:
                _safe_extract_tar(archive_path, extract_dir)
            _copy_tree_contents(extract_dir, root)
            acquired_source_path = extract_dir

        assert acquired_source_path is not None
        snapshot_archive = _save_workspace_snapshot_archive(
            ree_id,
            acquired_source_path,
            Path(urlparse(payload.originUrl).path).name or "source",
        )

    snapshot_captured_at = _utc_now()
    metadata["source"]["snapshotArchive"] = snapshot_archive
    metadata["source"]["snapshotCapturedAt"] = snapshot_captured_at

    metadata["status"] = "ready"
    ree = _ree_from_metadata(metadata).model_copy(
        update={
            "origin_url": payload.originUrl,
            "source_type": payload.sourceType,
        }
    )
    metadata["reeDraft"] = ree.with_source(metadata.get("source")).model_dump(
        by_alias=True, exclude_none=True
    )
    return get_workspace(ree_id, seed_metadata=_write_metadata(ree_id, metadata))


def init_source_upload(ree_id: str, payload: UploadInitPayload) -> dict[str, Any]:
    if not ree_dir(ree_id).exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    token = uuid.uuid4().hex
    return {
        "uploadUrl": f"/api/v1/rees/{ree_id}/source:upload/{token}",
        "uploadToken": token,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def _upload_stage_path(ree_id: str, token: str) -> Path:
    return ree_dir(ree_id) / f".upload.{token}.bin"


def store_source_upload_bytes(ree_id: str, token: str, data: bytes) -> dict[str, Any]:
    if not ree_dir(ree_id).exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    stage_path = _upload_stage_path(ree_id, token)
    stage_path.write_bytes(data)
    return {"uploadToken": token, "storedAt": _utc_now()}


def complete_source_upload(
    ree_id: str, upload_token: str, archive_name: str
) -> dict[str, Any]:
    root = workspace_dir(ree_id)
    if not root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    staged_archive = _upload_stage_path(ree_id, upload_token)
    staged_bytes = staged_archive.read_bytes() if staged_archive.exists() else b""
    _clear_workspace_content(ree_id)

    if staged_bytes:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(staged_bytes)
            tmp_path = Path(tmp.name)
        try:
            with tempfile.TemporaryDirectory() as extract_dir:
                extracted_source = Path(extract_dir)
                archive_suffix = archive_name.lower()
                if archive_suffix.endswith(".zip"):
                    _safe_extract_zip(tmp_path, extracted_source)
                else:
                    _safe_extract_tar(tmp_path, extracted_source)
                _copy_tree_contents(extracted_source, root)
                snapshot_archive = _save_workspace_snapshot_archive(
                    ree_id, extracted_source, archive_name
                )
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        (root / "README.md").write_text(
            f"# {archive_name}\n\nArchive upload completed without bytes.\n",
            encoding="utf-8",
        )
        snapshot_archive = _save_workspace_snapshot_archive(ree_id, root, archive_name)

    staged_archive.unlink(missing_ok=True)

    snapshot_captured_at = _utc_now()

    metadata = _read_metadata(ree_id)
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
        .model_dump(by_alias=True, exclude_none=True)
    )
    return {
        "sourceSnapshotId": upload_token,
        "status": "ready",
        "workspace": get_workspace(
            ree_id,
            seed_metadata=_write_metadata(ree_id, metadata),
        ),
    }


def remove_source(ree_id: str) -> dict[str, Any]:
    _clear_workspace_content(ree_id)
    metadata = _read_metadata(ree_id)
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
            }
        )
    )
    metadata["reeDraft"] = cleared_ree.model_dump(by_alias=True, exclude_none=True)
    return {
        "invalidatedSteps": ["source", "workflow"],
        "workspace": get_workspace(
            ree_id,
            seed_metadata=_write_metadata(ree_id, metadata),
        ),
    }
