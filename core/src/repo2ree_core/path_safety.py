"""Canonical lexical checks for user-supplied workspace-relative paths.

Leaf module: it imports nothing from ``repo2ree_core`` so the storage, domain,
and experiment layers can all share one definition of "is this a safe relative
path" without closing an import cycle (the same reason
``repo2ree_core.reserved_paths`` exists).

Two layers, used at different trust boundaries:

- :func:`validate_relative_path` is a *lexical* check — it rejects absolute
  paths and ``..`` traversal. The storage layer (``ReeLayout``, ``SubtreeStore``)
  relies on this alone: its subtrees hold REE-controlled content, so a lexical
  guard is sufficient there.
- :func:`resolve_within` layers the resolved
  (``Path.resolve().relative_to(...)``) escape check on top, which also catches
  symlink escapes. It is the guard for paths that come from author-supplied run
  scripts and declared outputs before they are handed to the shell or read back
  (see ``experiment/run.py``, ``run_script.py``,
  ``operations/steps/author.py``).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

# Leaf-file basename prefixes reserved for workspace control files
# (".workspace*", ".upload.*"). They name files, never directories, so callers
# guard only the leaf segment of a candidate path against them.
WORKSPACE_CONTROL_PREFIXES = (".workspace", ".upload.")


def resolve_within(base: Path, rel: str | PurePosixPath) -> Path | None:
    """Resolve *rel* under *base* and confirm it stays inside.

    The single, shared escape check: it runs the lexical
    :func:`validate_relative_path` guard, then resolves both paths (following
    symlinks) and confirms the candidate is still contained by *base*. Returns
    the resolved absolute path, or ``None`` when *rel* is unsafe or escapes —
    callers map ``None`` onto their own idiom (raise, skip, or fail the step).
    """
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

    # ── postcondition ──
    # The security boundary: a non-None result must never escape base. Re-checked
    # independently of the relative_to above so a future edit to the containment
    # logic can't silently start returning an escaping path.
    assert candidate.is_relative_to(base_resolved), f"resolve_within escaped base: {candidate}"  # noqa: S101
    # ───────────────────
    return candidate


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
    if pure.is_absolute() or text.startswith("/") or text.startswith("\\"):
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


def normalize_workspace_path(path: str | None) -> str:
    """Defensive cleanup for user-supplied workspace-relative paths.

    Strips surrounding whitespace and leading slashes. Permissive: returns
    ``""`` for falsy input and does not raise. Use :func:`validate_relative_path`
    when stricter checks are required.

    Whitespace and slashes interleave (``" /"``, ``"/ /x"``), and removing one
    exposes the other, so a single pass cannot settle it: ``" /"`` still ends up
    absolute whichever order the two strips run in. Both are therefore stripped
    to a fixpoint, which is what makes the result idempotent *and* never
    absolute. Whitespace is whatever ``str.strip`` considers it, so unicode
    spaces are handled too.
    """
    result = path or ""
    while True:
        stripped = result.strip().lstrip("/")
        if stripped == result:
            break
        result = stripped

    # ── postcondition ──
    assert not result.startswith("/"), f"normalized path must not be absolute: {result!r}"  # noqa: S101
    # ───────────────────
    return result
