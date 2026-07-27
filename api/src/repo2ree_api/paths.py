from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from repo2ree_core.path_safety import WORKSPACE_CONTROL_PREFIXES, resolve_within

__all__ = [
    "WORKSPACE_CONTROL_PREFIXES",
    "require_non_empty_path",
    "resolve_relative_path",
]


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
