from __future__ import annotations

from collections.abc import Callable, Sequence

from fastapi import HTTPException

_KEYSET_SEP = "~"


def keyset_paginate[ItemT](
    items: Sequence[ItemT],
    *,
    cursor: str | None,
    limit: int | None,
    key: Callable[[ItemT], tuple[str, str]],
) -> tuple[list[ItemT], str | None, bool]:
    if cursor is not None:
        sort_value, sep, tiebreak = cursor.partition(_KEYSET_SEP)
        if not sep:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_cursor",
                    "message": "Malformed pagination cursor",
                    "details": {"cursor": cursor},
                    "retryable": False,
                },
            )
        boundary = (sort_value, tiebreak)
        items = [item for item in items if key(item) < boundary]
    page = list(items if limit is None else items[: max(limit, 0)])
    has_more = len(page) < len(items)
    next_cursor = _KEYSET_SEP.join(key(page[-1])) if page and has_more else None
    return page, next_cursor, has_more
