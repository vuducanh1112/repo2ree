"""Transient host-side staging for HTTP uploads.

Uploaded bytes must land on control-plane disk before they are streamed to the
selected agent. The agent assembles the transfer and copies it into the
workbench, where ``extract_upload`` consumes it. This is the only host
persistence in the REE flow; it is keyed solely by upload token and holds no
per-REE durable state.

Guardrails: tokens are validated before they touch a path (a request-supplied
token must never escape the staging dir), and only *minted* tokens can land
bytes — ``new_upload_token`` creates an empty staged marker that the PUT
requires, so a request cannot invent tokens and write files. A single upload is
capped at ``UPLOAD_MAX_BYTES``, the staging dir as a whole at
``UPLOAD_STAGING_MAX_BYTES``, and files older than ``UPLOAD_TTL_SECONDS`` —
abandoned uploads that never reached upload-complete — are swept
opportunistically.
"""

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
from repo2ree_core.time_utils import iso_utc

# Minted tokens are uuid hex; accept a slightly wider single-path-component
# charset so the format is not load-bearing, but nothing that can traverse.
_TOKEN_RE = re.compile(r"[A-Za-z0-9._-]{1,128}")


class InvalidUploadTokenError(ValueError):
    """The upload token is not a safe single path component."""


class UnknownUploadTokenError(RuntimeError):
    """The upload token was never minted, or its staged file expired."""


class UploadTooLargeError(RuntimeError):
    """The upload body exceeded ``UPLOAD_MAX_BYTES``."""


class UploadStagingFullError(RuntimeError):
    """The staging dir has no room left under ``UPLOAD_STAGING_MAX_BYTES``."""


class UploadSizeMismatchError(RuntimeError):
    """The received byte count differs from the positive declared size."""


def _staging_root() -> Path:
    return service_settings.UPLOAD_STAGING_DIR


def ensure_staging_root() -> None:
    _staging_root().mkdir(parents=True, exist_ok=True)


def staged_upload_path(token: str) -> Path:
    if not _TOKEN_RE.fullmatch(token):
        raise InvalidUploadTokenError(f"invalid upload token {token!r}")
    return _staging_root() / f"{token}.bin"


def _upload_metadata_path(token: str) -> Path:
    staged_upload_path(token)  # validates the token
    return _staging_root() / f"{token}.json"


def new_upload_token(
    *,
    file_name: str | None = None,
    expected_size: int | None = None,
    content_type: str | None = None,
    ree_id: str = "",
    purpose: str = "",
) -> dict[str, str]:
    """Allocate an upload token and its expiry, minting its (empty) staged file.

    The empty file is the token's proof of mint: the PUT refuses tokens without
    one, and the TTL sweep reclaims it like any other staged file if the bytes
    never arrive."""
    # Each mint sweeps expired leftovers, so abandoned uploads cannot
    # accumulate on the host past their TTL.
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
            }
        ),
        encoding="utf-8",
    )
    ttl = timedelta(seconds=service_settings.UPLOAD_TTL_SECONDS)
    expires_at = iso_utc(datetime.now(UTC) + ttl)
    return {"upload_token": token, "expires_at": expires_at}


def validate_upload_owner(token: str, *, ree_id: str, purpose: str, file_name: str | None = None) -> None:
    """Require a token to belong to the addressed REE and upload workflow."""
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
    # What the rest of the staging dir leaves this upload under the global
    # budget, snapshotted once — concurrent uploads may overshoot by at most
    # one upload cap each, which is the accuracy this guardrail needs.
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
        # Reset to the minted marker rather than deleting: the token stays
        # valid for a retry PUT until its TTL.
        with suppress(OSError):
            path.write_bytes(b"")
        raise
    return path


def _staging_allowance(current: Path) -> int:
    """Bytes ``current`` may grow to before the staging dir exceeds its budget."""
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
    """Delete staged files older than the TTL (abandoned uploads)."""
    root = _staging_root()
    if not root.is_dir():
        return
    cutoff = time.time() - service_settings.UPLOAD_TTL_SECONDS
    for staged in root.glob("*.bin"):
        # A concurrent upload-complete may legitimately race the sweep.
        with suppress(OSError):
            if staged.stat().st_mtime < cutoff:
                token = staged.name.removesuffix(".bin")
                discard_staged_upload(token)
