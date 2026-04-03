from __future__ import annotations

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

from repo2ree.service.api.settings import service_settings


WorkspaceStatus = Literal["draft", "ready", "sealed", "archived"]


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


def workspace_dir(workspace_id: str) -> Path:
    return workspace_root() / workspace_id


def metadata_path(workspace_id: str) -> Path:
    return workspace_dir(workspace_id) / ".workspace.json"


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


def _default_workspace_name(workspace_id: str) -> str:
    return f"workspace-{workspace_id[:8]}"


def _default_metadata(workspace_id: str, name: str | None = None) -> dict[str, Any]:
    ts = _utc_now()
    return {
        "workspaceId": workspace_id,
        "externalRef": None,
        "name": name or _default_workspace_name(workspace_id),
        "status": "draft",
        "createdAt": ts,
        "updatedAt": ts,
        "reeDraft": {},
        "source": None,
    }


def _read_metadata(workspace_id: str) -> dict[str, Any]:
    path = metadata_path(workspace_id)
    if not path.exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")
    return _json_load(path)


def _write_metadata(workspace_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    metadata["updatedAt"] = _utc_now()
    _json_dump(metadata_path(workspace_id), metadata)
    return metadata


def read_workspace_metadata(workspace_id: str) -> dict[str, Any]:
    return _read_metadata(workspace_id)


def workspace_exists(workspace_id: str) -> bool:
    return metadata_path(workspace_id).exists()


def _resolve_workspace_path(workspace_id: str, path: str) -> Path:
    root = workspace_dir(workspace_id).resolve()
    candidate = (workspace_dir(workspace_id) / path).resolve()
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


def _iter_workspace_files(workspace_id: str):
    root = workspace_dir(workspace_id)
    if not root.exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if _is_metadata_file(file_path) or _is_upload_staging(file_path):
            continue
        yield file_path


def _relative_workspace_path(workspace_id: str, path: Path) -> str:
    return path.relative_to(workspace_dir(workspace_id)).as_posix()


def _file_kind(relative_path: str) -> str:
    if "/" not in relative_path and relative_path.lower().startswith("docker"):
        return "source"
    return "source"


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


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


def list_files(workspace_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for file_path in _iter_workspace_files(workspace_id):
        relative_path = _relative_workspace_path(workspace_id, file_path)
        entries.append({"path": relative_path, "kind": _file_kind(relative_path)})
    return entries


def _workspace_files_with_content(workspace_id: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for file_path in _iter_workspace_files(workspace_id):
        relative_path = _relative_workspace_path(workspace_id, file_path)
        entries.append(
            {
                "path": relative_path,
                "kind": _file_kind(relative_path),
                "content": _read_text_if_possible(file_path),
            }
        )
    return entries


def get_workspace(
    workspace_id: str, seed_metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    metadata = seed_metadata or _read_metadata(workspace_id)
    detail = dict(metadata)
    detail["files"] = _workspace_files_with_content(workspace_id)
    return detail


def _clear_workspace_content(workspace_id: str) -> None:
    root = workspace_dir(workspace_id)
    if not root.exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")
    for item in root.iterdir():
        if item.name == ".workspace.json":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink(missing_ok=True)


def create_workspace(payload: WorkspaceCreatePayload) -> dict[str, Any]:
    ensure_workspace_root()
    workspace_id = uuid.uuid4().hex
    root = workspace_dir(workspace_id)
    root.mkdir(parents=True, exist_ok=True)

    metadata = _default_metadata(workspace_id, payload.name)
    if payload.sourceMode == "url" and payload.originUrl and payload.sourceType:
        metadata["externalRef"] = payload.originUrl
        metadata["reeDraft"] = {
            "name": payload.name or metadata["name"],
            "origin_url": payload.originUrl,
            "source_type": payload.sourceType,
        }
        metadata = _write_metadata(workspace_id, metadata)
        acquire_source(
            workspace_id,
            SourceAcquirePayload(
                originUrl=payload.originUrl, sourceType=payload.sourceType
            ),
        )
        return get_workspace(workspace_id)

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

    return get_workspace(
        workspace_id, seed_metadata=_write_metadata(workspace_id, metadata)
    )


def patch_workspace(
    workspace_id: str, patch_payload: WorkspacePatchPayload
) -> dict[str, Any]:
    metadata = _read_metadata(workspace_id)
    ree_patch = dict(patch_payload.reePatch or {})
    metadata.setdefault("reeDraft", {})
    metadata["reeDraft"].update(ree_patch)
    if "name" in ree_patch and ree_patch["name"]:
        metadata["name"] = str(ree_patch["name"])
    return get_workspace(
        workspace_id, seed_metadata=_write_metadata(workspace_id, metadata)
    )


def delete_workspace(workspace_id: str) -> None:
    root = workspace_dir(workspace_id)
    if not root.exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")
    shutil.rmtree(root)


def read_file_content(workspace_id: str, path: str) -> dict[str, Any]:
    file_path = _resolve_workspace_path(workspace_id, path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(path)
    return {"content": file_path.read_text(encoding="utf-8"), "updatedAt": _utc_now()}


def write_file_content(workspace_id: str, path: str, content: str) -> dict[str, Any]:
    file_path = _resolve_workspace_path(workspace_id, path)
    _ensure_parent(file_path)
    file_path.write_text(content, encoding="utf-8")
    _write_metadata(workspace_id, _read_metadata(workspace_id))
    return {"etag": None, "updatedAt": _utc_now()}


def delete_file_content(workspace_id: str, path: str) -> dict[str, Any]:
    file_path = _resolve_workspace_path(workspace_id, path)
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(path)
    file_path.unlink()
    _write_metadata(workspace_id, _read_metadata(workspace_id))
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


def acquire_source(workspace_id: str, payload: SourceAcquirePayload) -> dict[str, Any]:
    root = workspace_dir(workspace_id)
    if not root.exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")

    _clear_workspace_content(workspace_id)

    metadata = _read_metadata(workspace_id)
    metadata["externalRef"] = payload.originUrl
    metadata["source"] = {
        "mode": "download",
        "originUrl": payload.originUrl,
        "sourceType": payload.sourceType,
        "acquiredAt": _utc_now(),
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
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
        else:
            archive_name = _safe_filename(
                Path(urlparse(payload.originUrl).path).name, "source.archive"
            )
            archive_path = tmp_dir_path / archive_name
            _download_or_open_local(payload.originUrl, archive_path)
            if payload.sourceType == "zip" or archive_path.suffix.lower() == ".zip":
                _safe_extract_zip(archive_path, root)
            else:
                _safe_extract_tar(archive_path, root)

    metadata["status"] = "ready"
    return get_workspace(
        workspace_id, seed_metadata=_write_metadata(workspace_id, metadata)
    )


def init_source_upload(workspace_id: str, payload: UploadInitPayload) -> dict[str, Any]:
    if not workspace_dir(workspace_id).exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")

    token = uuid.uuid4().hex
    return {
        "uploadUrl": f"/api/v1/workspaces/{workspace_id}/source:upload/{token}",
        "uploadToken": token,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(hours=1))
        .isoformat()
        .replace("+00:00", "Z"),
    }


def _upload_stage_path(workspace_id: str, token: str) -> Path:
    return workspace_dir(workspace_id) / f".upload.{token}.bin"


def store_source_upload_bytes(
    workspace_id: str, token: str, data: bytes
) -> dict[str, Any]:
    if not workspace_dir(workspace_id).exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")
    stage_path = _upload_stage_path(workspace_id, token)
    stage_path.write_bytes(data)
    return {"uploadToken": token, "storedAt": _utc_now()}


def complete_source_upload(
    workspace_id: str, upload_token: str, archive_name: str
) -> dict[str, Any]:
    root = workspace_dir(workspace_id)
    if not root.exists():
        raise FileNotFoundError(f"Workspace {workspace_id} not found")

    staged_archive = _upload_stage_path(workspace_id, upload_token)
    staged_bytes = staged_archive.read_bytes() if staged_archive.exists() else b""
    _clear_workspace_content(workspace_id)

    if staged_bytes:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(staged_bytes)
            tmp_path = Path(tmp.name)
        try:
            archive_suffix = archive_name.lower()
            if archive_suffix.endswith(".zip"):
                _safe_extract_zip(tmp_path, root)
            else:
                _safe_extract_tar(tmp_path, root)
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        (root / "README.md").write_text(
            f"# {archive_name}\n\nArchive upload completed without bytes.\n",
            encoding="utf-8",
        )

    staged_archive.unlink(missing_ok=True)

    metadata = _read_metadata(workspace_id)
    metadata["status"] = "ready"
    metadata["source"] = {
        "mode": "upload",
        "archiveName": archive_name,
        "uploadToken": upload_token,
        "completedAt": _utc_now(),
    }
    return {
        "sourceSnapshotId": upload_token,
        "status": "ready",
        "workspace": get_workspace(
            workspace_id,
            seed_metadata=_write_metadata(workspace_id, metadata),
        ),
    }


def remove_source(workspace_id: str) -> dict[str, Any]:
    _clear_workspace_content(workspace_id)
    metadata = _read_metadata(workspace_id)
    metadata["status"] = "draft"
    metadata["source"] = None
    return {
        "invalidatedSteps": ["source", "workflow"],
        "workspace": get_workspace(
            workspace_id,
            seed_metadata=_write_metadata(workspace_id, metadata),
        ),
    }
