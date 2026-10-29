"""Canonical lexical checks for user-supplied workspace-relative paths.

Leaf module: it imports nothing from ``repo2ree_core`` so the storage, domain,
and experiment layers can all share one definition of "is this a safe relative
path" without closing an import cycle.

Two layers, used at different trust boundaries:

- :func:`repo2ree_ree.paths.validate_relative_path` is a *lexical* check — it rejects absolute
  paths and ``..`` traversal. The storage layer (``ReeLayout``, ``SubtreeStore``)
  relies on this alone: its subtrees hold REE-controlled content, so a lexical
  guard is sufficient there.
- :func:`resolve_within` layers the resolved
  (``Path.resolve().relative_to(...)``) escape check on top, which also catches
  symlink escapes. It is the guard for paths that come from author-supplied run
  scripts and declared outputs before they are handed to the shell or read back
  (see ``execution/process.py`` and ``operations/read_models/files.py``).
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from repo2ree_ree.paths import validate_relative_path

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
