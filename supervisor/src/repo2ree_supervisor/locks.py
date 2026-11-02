"""One lock per REE, shared by everything that must not overlap on the same REE."""

from __future__ import annotations

import threading


class ReeLocks:
    """A command, a locked query, and setting up or tearing down a workbench never overlap on one REE."""

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def __call__(self, ree_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(ree_id, threading.Lock())
