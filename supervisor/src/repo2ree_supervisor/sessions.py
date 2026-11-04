"""A workbench's connection as the behaviour journal records it: one WorkbenchSession per socket.

The session is opened when the workbench says hello, then connected or refused, and lost when
its socket ends, by whichever way ends it first. It is partitioned by the store it claims only
when that store is registered: a hello names its store before any token is checked.
"""

from __future__ import annotations

import threading
from uuid import uuid4

from repo2ree_protocol.workbench import WorkbenchHello
from repo2ree_telemetry.behaviour import events


class Session:
    """One socket's WorkbenchSession; each transition is journaled once, in order, and never after it settled."""

    def __init__(self, hello: WorkbenchHello, *, registered: bool) -> None:
        self.session_id = uuid4().hex
        self._hello = hello
        self._partition = hello.store_id if registered else None
        self._state: events.WorkbenchSessionState | None = None
        self._lock = threading.Lock()
        self._move(None, "opened", {})

    def refuse(self, reason: events.WorkbenchSessionReason) -> None:
        self._move("opened", "refused", {"reason": reason})

    def connect(self) -> None:
        hello = self._hello
        self._move(
            "opened", "connected", {"backend": hello.backend, "slots": hello.slots, "version": hello.version or None}
        )

    def lose(self, reason: events.WorkbenchSessionReason, close_code: int | None = None) -> None:
        """The socket ended; only the first way it ended is recorded, and only for a connected session."""
        self._move("connected", "lost", {"reason": reason, "close_code": close_code})

    def _move(
        self,
        current: events.WorkbenchSessionState | None,
        target: events.WorkbenchSessionState,
        facts: events.WorkbenchSessionFacts,
    ) -> None:
        with self._lock:
            if self._state != current:
                return
            self._state = target
            hello = self._hello
            events.workbench_session(
                self.session_id,
                current,
                target,
                partition=self._partition,
                facts={"workbench_id": hello.workbench_id, "nonce": hello.nonce, "store_id": hello.store_id, **facts},
            )
