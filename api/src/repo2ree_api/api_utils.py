from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES, resolve_within

__all__ = [
    "WORKSPACE_CONTROL_PREFIXES",
    "keyset_paginate",
    "require_non_empty_path",
    "resolve_relative_path",
]


# ================================================
# Helpers
# ================================================


_KEYSET_SEP = "~"


def keyset_paginate(
    items: Sequence[dict[str, Any]],
    *,
    cursor: str | None,
    limit: int | None,
    key: Callable[[dict[str, Any]], tuple[str, str]],
) -> tuple[list[dict[str, Any]], str | None, bool]:
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


def require_non_empty_path(path_value: str | None, field_name: str) -> str:
    path = (path_value or "").strip()
    if not path:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return path


def resolve_relative_path(
    root: Path,
    relative_path: str,
    *,
    invalid_detail: str,
    blocked_prefixes: tuple[str, ...] = (),
) -> Path:
    """HTTP-facing wrapper around the shared containment check.

    The escape rule itself is ``path_safety.resolve_within`` — one definition
    for both trust boundaries, so the API cannot drift from what the workbench
    enforces. This layer only maps "unsafe" onto a 400 and adds the
    control-file basename guard the HTTP surface needs.
    """
    candidate = resolve_within(root, relative_path)
    if candidate is None:
        raise HTTPException(status_code=400, detail=invalid_detail)
    if blocked_prefixes and candidate.name.startswith(blocked_prefixes):
        raise HTTPException(status_code=400, detail=invalid_detail)
    return candidate
