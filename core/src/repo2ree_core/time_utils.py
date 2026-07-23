from __future__ import annotations

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
