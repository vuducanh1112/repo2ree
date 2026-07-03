from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES

__all__ = [
    "WORKSPACE_CONTROL_PREFIXES",
    "paginate",
    "require_non_empty_path",
    "resolve_relative_path",
]


# ================================================
# Helpers
# ================================================


def paginate(
    items: Sequence[dict[str, Any]], cursor: str | None, limit: int | None
) -> tuple[list[dict[str, Any]], str | None, bool]:
    start = 0
    if cursor:
        try:
            start = max(int(cursor), 0)
        except ValueError:
            start = 0
    end = len(items)
    if limit is not None and limit >= 0:
        end = min(start + limit, len(items))
    page = list(items[start:end])
    has_more = end < len(items)
    next_cursor = str(end) if has_more else None
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
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=invalid_detail) from exc
    if blocked_prefixes and candidate.name.startswith(blocked_prefixes):
        raise HTTPException(status_code=400, detail=invalid_detail)
    return candidate
