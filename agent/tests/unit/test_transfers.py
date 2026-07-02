"""Chunked copy-in reassembly on the agent side."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from repo2ree_agent.transfers import TransferStore


def test_deliver_reassembles_chunks_and_cleans_up() -> None:
    store = TransferStore()
    transfer_id = store.open("wb", "/ree/dest.bin")
    # Chunks are pipelined and may apply out of order; each carries its offset.
    store.write(transfer_id, 6, b"world")
    store.write(transfer_id, 0, b"hello ")

    landed: dict[str, str] = {}
    contents: dict[str, bytes] = {}

    def sink(container_name: str, source_path: str, container_path: str) -> None:
        landed["container_name"] = container_name
        landed["container_path"] = container_path
        landed["source_path"] = source_path
        contents["data"] = Path(source_path).read_bytes()

    store.deliver(transfer_id, sink)

    assert contents["data"] == b"hello world"
    assert landed["container_name"] == "wb"
    assert landed["container_path"] == "/ree/dest.bin"
    # The temp file is gone once delivered, and the handle is no longer tracked.
    assert not os.path.exists(landed["source_path"])
    with pytest.raises(KeyError):
        store.write(transfer_id, 11, b"more")


def test_deliver_removes_temp_file_even_when_sink_raises() -> None:
    store = TransferStore()
    transfer_id = store.open("wb", "/ree/dest.bin")
    store.write(transfer_id, 0, b"data")

    captured: dict[str, str] = {}

    def failing_sink(container_name: str, source_path: str, container_path: str) -> None:
        captured["source_path"] = source_path
        raise RuntimeError("docker cp failed")

    with pytest.raises(RuntimeError, match="docker cp failed"):
        store.deliver(transfer_id, failing_sink)

    assert not os.path.exists(captured["source_path"])


def test_abort_and_abort_all_discard_partial_files() -> None:
    store = TransferStore()
    aborted = store.open("wb", "/ree/a.bin")
    store.write(aborted, 0, b"partial")
    dangling = store.open("wb", "/ree/b.bin")

    store.abort(aborted)
    # Aborting an unknown/already-dropped transfer is a no-op.
    store.abort(aborted)
    with pytest.raises(KeyError):
        store.write(aborted, 7, b"more")

    store.abort_all()
    with pytest.raises(KeyError):
        store.write(dangling, 0, b"more")
