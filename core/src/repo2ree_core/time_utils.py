from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from repo2ree_ree.instant import UtcInstant as UtcInstant
from repo2ree_ree.instant import format_utc_instant as format_utc_instant
from repo2ree_ree.instant import iso_utc as iso_utc
from repo2ree_ree.instant import parse_utc_instant as parse_utc_instant


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string with a trailing 'Z'."""
    return iso_utc(datetime.now(UTC))


def utc_now_instant() -> UtcInstant:
    """Return the current UTC instant for typed domain state."""
    return datetime.now(UTC)


@dataclass(frozen=True)
class OperationTiming:
    """Completed operation timing suitable for a durable receipt."""

    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int


@dataclass(frozen=True)
class OperationTimer:
    """Wall timestamps plus monotonic elapsed time for one operation."""

    started_at: UtcInstant
    _started_ns: int

    @classmethod
    def start(cls) -> OperationTimer:
        return cls(started_at=utc_now_instant(), _started_ns=time.monotonic_ns())

    def finish(self) -> OperationTiming:
        return OperationTiming(
            started_at=self.started_at,
            finished_at=utc_now_instant(),
            duration_ms=max(0, (time.monotonic_ns() - self._started_ns) // 1_000_000),
        )


def format_duration_ms(duration_ms: int) -> str:
    """Compact human rendering while logs retain the exact millisecond value."""
    total_seconds, milliseconds = divmod(duration_ms, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    if total_seconds:
        return f"{total_seconds}.{milliseconds:03d}s"
    return f"{milliseconds}ms"
