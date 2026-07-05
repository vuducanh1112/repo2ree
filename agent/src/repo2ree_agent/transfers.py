"""Agent-side reassembly of a chunked byte transfer (the copy-in path).

The control plane streams a file to the agent in bounded chunks (see the wire
notes in ``repo2ree_protocol.agent``). Each open transfer is a temp file on the
agent host that chunks append to; on ``deliver`` the agent hands the finished
file to a sink (the runtime's ``copy_in``) and deletes it.

A ``TransferStore`` is scoped to one connection. If the connection drops with
transfers still open, ``abort_all`` discards their partial files — nothing leaks
past the life of the socket that created it.
"""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from repo2ree_protocol.agent import WorkbenchLocation

# ================================================
# Transfer store
# ================================================


@dataclass
class _Transfer:
    location: WorkbenchLocation
    container_path: str
    path: str
    handle: BinaryIO
    # Chunk requests are handled concurrently, so seek+write must be atomic
    # per transfer.
    write_lock: threading.Lock = field(default_factory=threading.Lock)


class TransferStore:
    """The transfers currently open on one agent connection."""

    def __init__(self) -> None:
        self._transfers: dict[str, _Transfer] = {}
        self._lock = threading.Lock()

    def open(self, location: WorkbenchLocation, container_path: str) -> str:
        """Start a transfer landing in ``container_path``; return its handle id."""
        fd, path = tempfile.mkstemp(prefix="repo2ree-copy-", suffix=".part")
        transfer = _Transfer(
            location=location,
            container_path=container_path,
            path=path,
            handle=os.fdopen(fd, "wb"),
        )
        transfer_id = uuid4().hex
        with self._lock:
            self._transfers[transfer_id] = transfer
        return transfer_id

    def write(self, transfer_id: str, offset: int, data: bytes) -> None:
        """Write one chunk at ``offset``. The control plane pipelines chunks and
        they apply out of order, so writes are positioned, not appended."""
        transfer = self._require(transfer_id)
        with transfer.write_lock:
            transfer.handle.seek(offset)
            transfer.handle.write(data)

    def deliver(self, transfer_id: str, sink: Callable[[WorkbenchLocation, str, str], None]) -> None:
        """Close the assembled file, hand it to ``sink(location, path,
        container_path)``, then delete the temp file — even if the sink raises."""
        with self._lock:
            transfer = self._transfers.pop(transfer_id, None)
        if transfer is None:
            raise KeyError(f"unknown transfer {transfer_id!r}")
        transfer.handle.close()
        try:
            sink(transfer.location, transfer.path, transfer.container_path)
        finally:
            Path(transfer.path).unlink(missing_ok=True)

    def abort(self, transfer_id: str) -> None:
        """Drop a transfer and its partial file (a no-op if already gone)."""
        with self._lock:
            transfer = self._transfers.pop(transfer_id, None)
        if transfer is not None:
            _discard(transfer)

    def abort_all(self) -> None:
        """Discard every still-open transfer — called when the connection drops."""
        with self._lock:
            transfers = list(self._transfers.values())
            self._transfers.clear()
        for transfer in transfers:
            _discard(transfer)

    def _require(self, transfer_id: str) -> _Transfer:
        with self._lock:
            transfer = self._transfers.get(transfer_id)
        if transfer is None:
            raise KeyError(f"unknown transfer {transfer_id!r}")
        return transfer


# ================================================
# Helpers
# ================================================


def _discard(transfer: _Transfer) -> None:
    with suppress(Exception):
        transfer.handle.close()
    Path(transfer.path).unlink(missing_ok=True)
