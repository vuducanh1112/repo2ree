from __future__ import annotations

import hashlib
import os
import secrets
import tempfile
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

TRANSFER_PATH_PREFIX = "/workbench/transfers/"


class TransferError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReceivedFile:
    path: Path
    size: int
    sha256: str


@dataclass
class _Upload:
    path: Path
    claimed: bool = False
    received: ReceivedFile | None = None


@dataclass
class _Offer:
    path: Path
    claimed: bool = False


def _token(transfer_path: str) -> str:
    return transfer_path.removeprefix(TRANSFER_PATH_PREFIX)


class Transfers:
    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory
        self._lock = threading.Lock()
        self._uploads: dict[str, _Upload] = {}
        self._offers: dict[str, _Offer] = {}

    def open_upload(self) -> str:
        token = secrets.token_urlsafe(32)
        handle, name = tempfile.mkstemp(prefix="repo2ree-transfer-", dir=self._directory)
        os.close(handle)
        with self._lock:
            self._uploads[token] = _Upload(Path(name))
        return TRANSFER_PATH_PREFIX + token

    async def receive(self, token: str, body: AsyncIterator[bytes], expected_size: int | None) -> ReceivedFile:
        with self._lock:
            upload = self._uploads.get(token)
            if upload is None or upload.claimed:
                raise TransferError("no such open transfer")
            upload.claimed = True
        digest = hashlib.sha256()
        size = 0
        with upload.path.open("wb") as target:
            async for chunk in body:
                target.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if expected_size is not None and size != expected_size:
            raise TransferError(f"upload ended after {size} of {expected_size} bytes")
        received = ReceivedFile(upload.path, size, digest.hexdigest())
        with self._lock:
            upload.received = received
        return received

    def collect(self, transfer_path: str) -> ReceivedFile:
        with self._lock:
            upload = self._uploads.pop(_token(transfer_path), None)
        if upload is None or upload.received is None:
            if upload is not None:
                upload.path.unlink(missing_ok=True)
            raise TransferError("the workbench answered done, but no complete upload arrived")
        return upload.received

    def discard(self, transfer_path: str) -> None:
        with self._lock:
            upload = self._uploads.pop(_token(transfer_path), None)
        if upload is not None:
            upload.path.unlink(missing_ok=True)

    def offer(self, path: Path) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._offers[token] = _Offer(path)
        return TRANSFER_PATH_PREFIX + token

    def serve(self, token: str) -> Path:
        with self._lock:
            offer = self._offers.get(token)
            if offer is None or offer.claimed:
                raise TransferError("no such open transfer")
            offer.claimed = True
        return offer.path

    def close(self, transfer_path: str) -> None:
        with self._lock:
            self._offers.pop(_token(transfer_path), None)
