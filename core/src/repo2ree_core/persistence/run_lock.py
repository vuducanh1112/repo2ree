from __future__ import annotations

import fcntl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO

from repo2ree_core.persistence.layout import ReeLayout

RUN_LOCK = "repo2ree.run.lock"


@contextmanager
def holding_ree(layout: ReeLayout, run_id: str) -> Iterator[str | None]:
    path = layout.git_dir / RUN_LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as lock:
        if not _try_lock(lock):
            lock.seek(0)
            yield lock.read().strip() or "unknown"
            return
        lock.seek(0)
        lock.truncate()
        lock.write(run_id)
        lock.flush()
        try:
            yield None
        finally:
            lock.truncate(0)
            fcntl.flock(lock, fcntl.LOCK_UN)


def _try_lock(lock: IO[str], kind: int = fcntl.LOCK_EX) -> bool:
    try:
        fcntl.flock(lock, kind | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def running_run(layout: ReeLayout) -> str | None:
    path = layout.git_dir / RUN_LOCK
    try:
        with path.open(encoding="utf-8") as lock:
            if not lock.read().strip() or _try_lock(lock, fcntl.LOCK_SH):
                return None
            lock.seek(0)
            return lock.read().strip() or "unknown"
    except FileNotFoundError:
        return None


def wait_until_free(layout: ReeLayout, *, timeout: float | None = None, poll: float = 0.5) -> str | None:
    first = running_run(layout)
    deadline = None if timeout is None else time.monotonic() + timeout
    while running_run(layout) is not None:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(f"the REE is still held by run {running_run(layout)}")
        time.sleep(poll)
    return first
