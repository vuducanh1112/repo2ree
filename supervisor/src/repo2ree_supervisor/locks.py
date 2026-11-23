from __future__ import annotations

import threading


class ReeLocks:
    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def __call__(self, ree_id: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(ree_id, threading.Lock())
