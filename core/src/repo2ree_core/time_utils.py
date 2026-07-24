from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime


def iso_utc(moment: datetime) -> str:
    """Format *moment* as an ISO-8601 string with a trailing 'Z'.

    One spelling of the timestamp format every recorded time uses, so a value
    computed from a future instant (an expiry, say) cannot end up shaped
    differently from one taken now.
    """
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string with a trailing 'Z'."""
    return iso_utc(datetime.now(UTC))


@dataclass(frozen=True)
class OperationTiming:
    """Completed operation timing suitable for a durable receipt."""

    started_at: str
    finished_at: str
    duration_ms: int


@dataclass(frozen=True)
class OperationTimer:
    """Wall timestamps plus monotonic elapsed time for one operation."""

    started_at: str
    _started_ns: int

    @classmethod
    def start(cls) -> OperationTimer:
        return cls(started_at=utc_now(), _started_ns=time.monotonic_ns())

    def finish(self) -> OperationTiming:
        return OperationTiming(
            started_at=self.started_at,
            finished_at=utc_now(),
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
