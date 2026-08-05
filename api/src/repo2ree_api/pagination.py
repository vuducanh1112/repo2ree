from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from fastapi import HTTPException

_KEYSET_SEP = "~"

# The paginated item. Generic because keyset pagination is about the *key*, not
# the payload: a route that projects a typed summary before paginating should
# not have to widen it back to a dict to get a page out.
ItemT = TypeVar("ItemT")


def keyset_paginate(
    items: Sequence[ItemT],
    *,
    cursor: str | None,
    limit: int | None,
    key: Callable[[ItemT], tuple[str, str]],
) -> tuple[list[ItemT], str | None, bool]:
    """Paginate a sequence sorted descending by ``key`` with a keyset cursor.

    ``key`` returns a (sort value, unique tiebreak) string pair; the cursor
    encodes the last returned item's key. Unlike an offset cursor, items
    created or deleted between pages cannot shift page boundaries — the next
    page is simply "everything strictly after the cursor key". Neither key
    component may contain the separator character.
    """
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
