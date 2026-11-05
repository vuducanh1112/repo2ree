"""The store's behaviour journal, kept in the store and written by the one workbench serving it."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from repo2ree_telemetry.behaviour import close_journal, open_journal

STATE = ".repo2ree"


class StoreHeldError(RuntimeError):
    pass


def journal_directory(store_root: Path) -> Path:
    return store_root / STATE / "journal"


@contextmanager
def store_journal(store_root: Path, store_id: str) -> Iterator[Path]:
    """Hold the store for this process and journal what it does there; refused while another process holds it."""
    directory = journal_directory(store_root)
    directory.mkdir(parents=True, exist_ok=True)
    lease = os.open(directory.parent / "workbench.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise StoreHeldError(f"store {store_id!r} at {store_root} is held by another workbench process") from None
        open_journal(directory, "workbench", hosts=("workbench",), instance=store_id)
        try:
            yield directory
        finally:
            close_journal()
    finally:
        os.close(lease)
