"""Chunked workbench copy-in reassembly on the agent side."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_agent.control.transfers import TransferStore
from repo2ree_protocol.agent import WorkbenchRef

_WB = WorkbenchRef(runtime="docker", token="wb")  # noqa: S106 - opaque reference


def test_deliver_reassembles_chunks_and_cleans_up() -> None:
    store = TransferStore()
    transfer_id = store.open(_WB, "/ree/dest.bin")
    # Chunks are pipelined and may apply out of order; each carries its offset.
    store.write(transfer_id, 6, b"world")
    store.write(transfer_id, 0, b"hello ")

    landed: dict[str, str] = {}
    contents: dict[str, bytes] = {}

    def sink(ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        landed["token"] = ref.token
        landed["workbench_path"] = workbench_path
        landed["source_path"] = source_path
        contents["data"] = Path(source_path).read_bytes()

    store.deliver(transfer_id, sink)

    assert contents["data"] == b"hello world"
    assert landed["token"] == "wb"  # noqa: S105 - opaque reference
    assert landed["workbench_path"] == "/ree/dest.bin"
    # The temp file is gone once delivered, and the handle is no longer tracked.
    assert not Path(landed["source_path"]).exists()
    with pytest.raises(KeyError):
        store.write(transfer_id, 11, b"more")


def test_deliver_removes_temp_file_even_when_sink_raises() -> None:
    store = TransferStore()
    transfer_id = store.open(_WB, "/ree/dest.bin")
    store.write(transfer_id, 0, b"data")

    captured: dict[str, str] = {}

    def failing_sink(ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        captured["source_path"] = source_path
        raise RuntimeError("docker cp failed")

    with pytest.raises(RuntimeError, match="docker cp failed"):
        store.deliver(transfer_id, failing_sink)

    assert not Path(captured["source_path"]).exists()


def test_abort_and_abort_all_discard_partial_files() -> None:
    store = TransferStore()
    aborted = store.open(_WB, "/ree/a.bin")
    store.write(aborted, 0, b"partial")
    dangling = store.open(_WB, "/ree/b.bin")

    store.abort(aborted)
    # Aborting an unknown/already-dropped transfer is a no-op.
    store.abort(aborted)
    with pytest.raises(KeyError):
        store.write(aborted, 7, b"more")

    store.abort_all()
    with pytest.raises(KeyError):
        store.write(dangling, 0, b"more")
