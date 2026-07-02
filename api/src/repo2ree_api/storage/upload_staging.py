"""Transient host-side staging for HTTP uploads.

Uploaded bytes must land on host disk before they can be ``docker cp``'d into a
workbench container, where ``extract_upload`` consumes them. This is the only
host persistence in the REE flow; it is keyed solely by upload token and holds
no per-REE workspace state.

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
import re
import time
import uuid
from collections.abc import AsyncIterable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from repo2ree_api.settings import service_settings

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


def _staging_root() -> Path:
    return service_settings.UPLOAD_STAGING_DIR


def ensure_staging_root() -> None:
    _staging_root().mkdir(parents=True, exist_ok=True)


def staged_upload_path(token: str) -> Path:
    if not _TOKEN_RE.fullmatch(token):
        raise InvalidUploadTokenError(f"invalid upload token {token!r}")
    return _staging_root() / f"{token}.bin"


def new_upload_token() -> dict[str, str]:
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
    ttl = timedelta(seconds=service_settings.UPLOAD_TTL_SECONDS)
    expires_at = (datetime.now(UTC) + ttl).isoformat().replace("+00:00", "Z")
    return {"uploadToken": token, "expiresAt": expires_at}


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
                staged.unlink(missing_ok=True)
