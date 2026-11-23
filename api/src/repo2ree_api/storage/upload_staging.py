from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from repo2ree_api.settings import service_settings
from repo2ree_ree.instant import format_utc_instant

_TOKEN_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")


class InvalidUploadTokenError(ValueError):
    pass


class UnknownUploadTokenError(RuntimeError):
    pass


class UploadTooLargeError(RuntimeError):
    pass


class UploadStagingFullError(RuntimeError):
    pass


class UploadSizeMismatchError(RuntimeError):
    pass


def _staging_root() -> Path:
    return service_settings.UPLOAD_STAGING_DIR


def ensure_staging_root() -> None:
    _staging_root().mkdir(parents=True, exist_ok=True)


def staged_upload_path(token: str) -> Path:
    if not _TOKEN_RE.fullmatch(token):
        raise InvalidUploadTokenError(f"invalid upload token {token!r}")
    return _staging_root() / f"{token}.bin"


def _upload_metadata_path(token: str) -> Path:
    staged_upload_path(token)
    return _staging_root() / f"{token}.json"


def new_upload_token(
    *,
    file_name: str | None = None,
    expected_size: int | None = None,
    content_type: str | None = None,
    ree_id: str = "",
    purpose: str = "",
    action_id: str | None = None,
) -> dict[str, str]:
    discard_expired_uploads()
    ensure_staging_root()
    token = uuid.uuid4().hex
    staged_upload_path(token).touch()
    _upload_metadata_path(token).write_text(
        json.dumps(
            {
                "file_name": file_name,
                "expected_size": expected_size,
                "content_type": content_type,
                "ree_id": ree_id,
                "purpose": purpose,
                "action_id": action_id,
            }
        ),
        encoding="utf-8",
    )
    ttl = timedelta(seconds=service_settings.UPLOAD_TTL_SECONDS)
    expires_at = format_utc_instant(datetime.now(UTC) + ttl)
    return {"upload_token": token, "expires_at": expires_at}


def upload_action_id(token: str) -> str | None:
    try:
        metadata = _read_upload_metadata(token)
    except (InvalidUploadTokenError, UnknownUploadTokenError, OSError, ValueError):
        return None
    action_id = metadata.get("action_id")
    return action_id if isinstance(action_id, str) else None


def validate_upload_owner(token: str, *, ree_id: str, purpose: str, file_name: str | None = None) -> None:
    path = staged_upload_path(token)
    if not path.exists():
        raise UnknownUploadTokenError(f"unknown or expired upload token {token!r}")
    metadata = _read_upload_metadata(token)
    if metadata.get("ree_id") != ree_id or metadata.get("purpose") != purpose:
        raise UnknownUploadTokenError(f"upload token {token!r} does not belong to this REE or upload type")
    expected_name = metadata.get("file_name")
    if file_name is not None and expected_name and expected_name != file_name:
        raise UploadSizeMismatchError(
            f"upload filename {file_name!r} does not match initialized filename {expected_name!r}"
        )


async def stage_upload_stream(token: str, chunks: AsyncIterable[bytes]) -> Path:
    path = staged_upload_path(token)
    if not path.exists():
        raise UnknownUploadTokenError(f"unknown or expired upload token {token!r}")
    max_bytes = service_settings.UPLOAD_MAX_BYTES
    allowance = min(max_bytes, _staging_allowance(path))
    total = 0
    try:
        with path.open("wb") as f:
            async for chunk in chunks:
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise UploadTooLargeError(f"upload exceeds the {max_bytes}-byte limit")
                if total > allowance:
                    raise UploadStagingFullError(
                        f"upload staging is out of space (budget {service_settings.UPLOAD_STAGING_MAX_BYTES} bytes)"
                    )
                await asyncio.to_thread(f.write, chunk)
        metadata = _read_upload_metadata(token)
        expected_size = metadata.get("expected_size")
        if isinstance(expected_size, int) and expected_size > 0 and total != expected_size:
            raise UploadSizeMismatchError(f"upload size {total} does not match declared size {expected_size}")
    except BaseException:
        with suppress(OSError):
            path.write_bytes(b"")
        raise
    return path


def _staging_allowance(current: Path) -> int:
    used = 0
    for staged in _staging_root().glob("*.bin"):
        if staged != current:
            with suppress(OSError):
                used += staged.stat().st_size
    return max(0, service_settings.UPLOAD_STAGING_MAX_BYTES - used)


def discard_staged_upload(token: str) -> None:
    staged_upload_path(token).unlink(missing_ok=True)
    _upload_metadata_path(token).unlink(missing_ok=True)


def _read_upload_metadata(token: str) -> dict[str, object]:
    path = _upload_metadata_path(token)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def discard_expired_uploads() -> None:
    root = _staging_root()
    if not root.is_dir():
        return
    cutoff = time.time() - service_settings.UPLOAD_TTL_SECONDS
    for staged in root.glob("*.bin"):
        with suppress(OSError):
            if staged.stat().st_mtime < cutoff:
                token = staged.name.removesuffix(".bin")
                discard_staged_upload(token)
