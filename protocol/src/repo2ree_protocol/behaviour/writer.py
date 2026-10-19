"""Durable, owner-written behaviour journals.

Each process writes one journal file per epoch: ``<process>-<epoch>.ndjson``.
Records carry a contiguous sequence number assigned here, so a reader can prove
that nothing between two records was lost. A record that cannot be written
still consumes its number: a failed write becomes a visible gap, never a
silent omission. Owners record after their own durable state change, so a
journal can lag its owner's state but never run ahead of it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace

from repo2ree_protocol.behaviour.machines import SPEC_DIGEST

_log = logging.getLogger(__name__)

type Fact = str | int | bool | None

_NAME = re.compile(r"^(?P<process>[a-z][a-z0-9-]*)-(?P<epoch>[0-9]{6})\.ndjson$")


class Journal:
    """The recording interface owners call. The base class records nothing."""

    def transition(
        self,
        owner: str,
        entity: str,
        key: str,
        current: str | None,
        target: str,
        *,
        partition: str | None,
        facts: Mapping[str, Fact] | None = None,
    ) -> None:
        self._record(
            {
                "kind": "transition",
                "owner": owner,
                "subject": entity,
                "key": key,
                "partition": partition,
                "from": current,
                "to": target,
                "facts": dict(facts or {}),
            }
        )

    def send(
        self,
        owner: str,
        boundary: str,
        message: str,
        key: str,
        *,
        partition: str | None,
        facts: Mapping[str, Fact] | None = None,
    ) -> str | None:
        """Record a request; returns its reference (``<journal>#<seq>``) for the receiver to cite, if written."""
        return self._message("send", owner, boundary, message, key, partition, facts)

    def receive(
        self,
        owner: str,
        boundary: str,
        message: str,
        key: str,
        *,
        partition: str | None,
        facts: Mapping[str, Fact] | None = None,
    ) -> None:
        self._message("receive", owner, boundary, message, key, partition, facts)

    def abandon(self, owner: str, boundary: str, key: str, *, partition: str | None, reason: str) -> None:
        """The sender stopped waiting without receiving any response."""
        self._message("abandon", owner, boundary, None, key, partition, {"reason": reason})

    def close(self) -> None:
        return None

    def _message(
        self,
        kind: str,
        owner: str,
        boundary: str,
        message: str | None,
        key: str,
        partition: str | None,
        facts: Mapping[str, Fact] | None,
    ) -> str | None:
        return self._record(
            {
                "kind": kind,
                "owner": owner,
                "subject": boundary,
                "key": key,
                "partition": partition,
                "message": message,
                "facts": dict(facts or {}),
            }
        )

    def _record(self, record: dict[str, Any]) -> str | None:
        """Write one record; its reference when it was written, else None."""
        return None


class FileJournal(Journal):
    def __init__(self, directory: Path, process: str, hosts: Iterable[str]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.process = process
        self._lock = threading.Lock()
        self._sequence = 0
        self._closed = False
        while True:
            epochs = [
                int(match["epoch"])
                for path in directory.glob(f"{process}-*.ndjson")
                if (match := _NAME.match(path.name)) and match["process"] == process
            ]
            self.epoch = max(epochs, default=0) + 1
            self.path = directory / f"{process}-{self.epoch:06d}.ndjson"
            try:
                # Exclusive creation: two processes can never share an epoch.
                self._stream = self.path.open("x", encoding="utf-8")
                break
            except FileExistsError:
                continue
        self._append(
            {
                "kind": "journal.opened",
                "process": process,
                "epoch": self.epoch,
                "hosts": sorted(set(hosts) | {process}),
                "spec_digest": SPEC_DIGEST,
                "pid": os.getpid(),
            }
        )

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
        self._append({"kind": "journal.closed"})
        with self._lock:
            self._closed = True
            self._stream.close()

    def _record(self, record: dict[str, Any]) -> str | None:
        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            record["trace"] = {"trace_id": f"{context.trace_id:032x}", "span_id": f"{context.span_id:016x}"}
        seq = self._append(record)
        return None if seq is None else f"{self.path.stem}#{seq}"

    def _append(self, record: dict[str, Any]) -> int | None:
        """Write one record; its sequence number when it was written, else None."""
        with self._lock:
            if self._closed:
                _log.error("behaviour journal %s is closed; dropping %s", self.path.name, record.get("kind"))
                return None
            self._sequence += 1
            line = json.dumps(
                {"v": 1, "seq": self._sequence, **record, "at": datetime.now(UTC).isoformat()},
                separators=(",", ":"),
                sort_keys=True,
            )
            try:
                self._stream.write(line + "\n")
                self._stream.flush()
                os.fsync(self._stream.fileno())
            except (OSError, ValueError):
                # The sequence number stays consumed, so the loss is visible to readers.
                _log.exception("behaviour journal %s lost seq %d", self.path.name, self._sequence)
                return None
            return self._sequence


_current: Journal = Journal()
_current_lock = threading.Lock()


def open_journal(directory: Path, process: str, hosts: Iterable[str] = ()) -> FileJournal:
    """Start this process's journal epoch; replaces (and closes) any previous one."""
    global _current
    opened = FileJournal(directory, process, hosts)
    with _current_lock:
        previous, _current = _current, opened
    previous.close()
    return opened


def close_journal() -> None:
    global _current
    with _current_lock:
        previous, _current = _current, Journal()
    previous.close()


def journal() -> Journal:
    return _current
