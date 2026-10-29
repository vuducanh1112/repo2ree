from __future__ import annotations

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
