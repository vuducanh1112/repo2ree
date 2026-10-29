from __future__ import annotations

from pathlib import PurePosixPath


def validate_relative_path(rel: str | PurePosixPath) -> None:
    """Reject absolute paths and parent traversals.

    Pure validator intended to run before any path is handed to the shell.
    """
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
    """Reject anything that is not a single, safe path segment.

    The guard for the *identifiers* an REE layout keys directories and files by
    — run ids, review ids, upload tokens. They are stricter than a relative path
    because they may never be one: a separator would let a caller name a sibling
    tree, and a leading dot would collide with the reserved control files that
    file enumeration deliberately skips.

    ``kind`` names the identifier in the error, so a rejection says which of them
    was malformed. Returns *value* so a caller can validate in the expression
    that consumes it.
    """
    if not value or "/" in value or "\\" in value or value.startswith("."):
        raise ValueError(f"invalid {kind}: {value!r}")
    return value
