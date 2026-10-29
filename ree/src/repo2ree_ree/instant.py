from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, PlainSerializer, TypeAdapter


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def format_utc_instant(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


UtcInstant = Annotated[
    datetime,
    AfterValidator(_normalize_utc),
    PlainSerializer(format_utc_instant, return_type=str, when_used="json"),
]

_UTC_INSTANT_ADAPTER: TypeAdapter[UtcInstant] = TypeAdapter(UtcInstant)


def parse_utc_instant(value: str | datetime) -> UtcInstant:
    return _UTC_INSTANT_ADAPTER.validate_python(value)
