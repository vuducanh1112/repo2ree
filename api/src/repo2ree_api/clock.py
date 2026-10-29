from __future__ import annotations

from datetime import UTC, datetime

from repo2ree_ree.instant import iso_utc


def utc_now() -> str:
    return iso_utc(datetime.now(UTC))
