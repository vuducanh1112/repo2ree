"""Files moving between the control plane and workbenches over HTTP, beside their control sockets.

Bulk bytes do not travel as frames on a workbench's control socket: there they
queue ahead of keepalive pings and every other request for that bench, until a
large enough file closes the connection. Instead the caller opens a transfer here
and names its path in a request; the workbench moves the bytes over HTTP to or from
``/workbench/transfers/<token>`` on the address it already dials, and answers
``done`` on the socket. Both directions:

- out of the bench (``ExecUploadRequest``): :meth:`Transfers.open_upload`; the
  workbench ``PUT``s the file, the HTTP route writes it in (:meth:`Transfers.receive`),
  and the caller :meth:`Transfers.collect`\\ s it once the request is done;
- into the bench (``FetchFileRequest``): :meth:`Transfers.offer` a local file; the
  workbench ``GET``s it, the HTTP route hands it out once (:meth:`Transfers.serve`),
  and the caller :meth:`Transfers.close`\\ s the transfer when the request ends.

A token is the transfer's only credential: random, unguessable, and good for one
upload or one download while its caller waits. Nothing here is persistent — a
restart drops every open transfer, and the requests waiting on them fail as their
workbench connection does.
"""

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
    """An upload that did not arrive whole, or a transfer that is not open."""


@dataclass(frozen=True)
class ReceivedFile:
    """A finished upload: the caller owns ``path`` and removes it when done."""

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
    """Open transfers by token: files workbenches may upload, or fetch, exactly once."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory
        self._lock = threading.Lock()
        self._uploads: dict[str, _Upload] = {}
        self._offers: dict[str, _Offer] = {}

    # ---- out of the bench --------------------------------------------------

    def open_upload(self) -> str:
        """A transfer a workbench uploads into; the path is what an ``ExecUploadRequest`` names."""
        token = secrets.token_urlsafe(32)
        handle, name = tempfile.mkstemp(prefix="repo2ree-transfer-", dir=self._directory)
        os.close(handle)
        with self._lock:
            self._uploads[token] = _Upload(Path(name))
        return TRANSFER_PATH_PREFIX + token

    async def receive(self, token: str, body: AsyncIterator[bytes], expected_size: int | None) -> ReceivedFile:
        """Write one upload's body into its transfer; refuses an unknown or already-used token."""
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
        """The finished file of an upload, which closes it; TransferError if nothing arrived whole."""
        with self._lock:
            upload = self._uploads.pop(_token(transfer_path), None)
        if upload is None or upload.received is None:
            if upload is not None:
                upload.path.unlink(missing_ok=True)
            raise TransferError("the workbench answered done, but no complete upload arrived")
        return upload.received

    def discard(self, transfer_path: str) -> None:
        """Close an upload whose request failed, removing whatever arrived."""
        with self._lock:
            upload = self._uploads.pop(_token(transfer_path), None)
        if upload is not None:
            upload.path.unlink(missing_ok=True)

    # ---- into the bench ----------------------------------------------------

    def offer(self, path: Path) -> str:
        """A transfer a workbench fetches ``path`` from; the path is what a ``FetchFileRequest`` names.

        The file stays the caller's: closing the transfer forgets it, never deletes it.
        """
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._offers[token] = _Offer(path)
        return TRANSFER_PATH_PREFIX + token

    def serve(self, token: str) -> Path:
        """The offered file, once; refuses an unknown or already-fetched token."""
        with self._lock:
            offer = self._offers.get(token)
            if offer is None or offer.claimed:
                raise TransferError("no such open transfer")
            offer.claimed = True
        return offer.path

    def close(self, transfer_path: str) -> None:
        """Forget an offer: its request ended, whatever the outcome."""
        with self._lock:
            self._offers.pop(_token(transfer_path), None)
