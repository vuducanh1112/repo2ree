from __future__ import annotations

from datetime import UTC, datetime

from repo2ree_ree.instant import format_utc_instant


def utc_now() -> str:
    return format_utc_instant(datetime.now(UTC))
