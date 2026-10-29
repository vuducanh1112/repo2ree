from __future__ import annotations

from pathlib import Path, PurePosixPath


def validate_relative_path(rel: str | PurePosixPath) -> None:
    if not isinstance(rel, str | PurePosixPath):
        raise TypeError(f"relative path must be str or PurePosixPath, got {type(rel).__name__}")
    text = str(rel)
    if text == "":
        raise ValueError("relative path must not be empty")
    pure = PurePosixPath(text)
    if pure.is_absolute() or text.startswith(("/", "\\")):
        raise ValueError(f"relative path must not be absolute: {text!r}")
    if any(part == ".." for part in pure.parts):
        raise ValueError(f"relative path must not contain '..': {text!r}")


def validate_path_segment(value: str, *, kind: str) -> str:
    if not value or "/" in value or "\\" in value or value.startswith("."):
        raise ValueError(f"invalid {kind}: {value!r}")
    return value


def resolve_within(base: Path, rel: str | PurePosixPath) -> Path | None:
    try:
        validate_relative_path(rel)
    except (TypeError, ValueError):
        return None
    base_resolved = base.resolve()
    candidate = (base_resolved / Path(str(rel))).resolve()
    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        return None

    assert candidate.is_relative_to(base_resolved), f"resolve_within escaped base: {candidate}"  # noqa: S101
    return candidate
