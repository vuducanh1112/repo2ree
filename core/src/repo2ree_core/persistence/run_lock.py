"""One command runs in an REE at a time: the process running it holds the REE's run lock, which names the run.

The lock sits beside the history lock a capture takes, in ``.git``, which no capture commits. The kernel releases
it with the process that held it, however that process ended.
"""

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
    """Hold the REE for this run; yields None once held, or the run id of the one holding it.

    The kernel releases the lock with the process that held it, however that process ended, so an REE is never
    left held by a run that is gone, and an attempt found pending while the lock is held is one that ended.
    """
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
    """The run holding the REE, or None when no command runs in it."""
    path = layout.git_dir / RUN_LOCK
    try:
        with path.open(encoding="utf-8") as lock:
            # A holder that was killed leaves its run id behind, but not its lock.
            if not lock.read().strip() or _try_lock(lock, fcntl.LOCK_SH):
                return None
            lock.seek(0)
            return lock.read().strip() or "unknown"
    except FileNotFoundError:
        return None


def wait_until_free(layout: ReeLayout, *, timeout: float | None = None, poll: float = 0.5) -> str | None:
    """Wait until no command runs in the REE; the run that held it when the wait began, or None.

    Raises ``TimeoutError`` when the REE is still held after ``timeout`` seconds.
    """
    first = running_run(layout)
    deadline = None if timeout is None else time.monotonic() + timeout
    while running_run(layout) is not None:
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError(f"the REE is still held by run {running_run(layout)}")
        time.sleep(poll)
    return first
