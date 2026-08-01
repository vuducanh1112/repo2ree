from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer, TypeAdapter


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _serialize_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcInstant = Annotated[
    datetime,
    AfterValidator(_normalize_utc),
    PlainSerializer(_serialize_utc, return_type=str, when_used="json"),
]

_UTC_INSTANT_ADAPTER: TypeAdapter[UtcInstant] = TypeAdapter(UtcInstant)


def parse_utc_instant(value: str | datetime) -> UtcInstant:
    return _UTC_INSTANT_ADAPTER.validate_python(value)


def format_utc_instant(value: UtcInstant) -> str:
    return _serialize_utc(value)


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
