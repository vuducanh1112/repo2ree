"""Transient host-side staging for HTTP uploads.

Uploaded bytes must land on host disk before they can be ``docker cp``'d into a
workbench container, where ``extract_upload`` consumes them. This is the only
host persistence in the REE flow; it is keyed solely by upload token and holds
no per-REE workspace state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from repo2ree_api.settings import service_settings


def _staging_root() -> Path:
    return service_settings.UPLOAD_STAGING_DIR


def ensure_staging_root() -> None:
    _staging_root().mkdir(parents=True, exist_ok=True)


def staged_upload_path(token: str) -> Path:
    return _staging_root() / f"{token}.bin"


def new_upload_token() -> dict[str, str]:
    """Allocate an upload token and its expiry (no bytes written yet)."""
    import uuid

    token = uuid.uuid4().hex
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    return {"uploadToken": token, "expiresAt": expires_at}


def stage_upload_bytes(token: str, data: bytes) -> Path:
    ensure_staging_root()
    path = staged_upload_path(token)
    path.write_bytes(data)
    return path


def discard_staged_upload(token: str) -> None:
    staged_upload_path(token).unlink(missing_ok=True)
