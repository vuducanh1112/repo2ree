"""Example-based checks for the path guards that need a real filesystem.

The generative invariants live in ``test_path_safety_properties.py``; this file
covers the symlink-escape case, which the pure/lexical properties can't reach
because it depends on an actual symlink resolving outside the base.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.path_safety import resolve_within


def test_symlink_escaping_base_is_rejected(tmp_path: Path) -> None:
    """A lexically-valid path whose symlink resolves outside base returns None.

    ``escape`` passes validate_relative_path (no ``..``, not absolute), so only
    the resolved-containment check catches it — the guard resolve_within layers
    on top of the lexical validator.
    """
    base = tmp_path / "workspace"
    base.mkdir()
    outside = tmp_path / "secret"
    outside.mkdir()
    (base / "escape").symlink_to(outside)

    assert resolve_within(base, "escape/file.txt") is None


def test_symlink_staying_inside_base_is_allowed(tmp_path: Path) -> None:
    base = tmp_path / "workspace"
    base.mkdir()
    (base / "real").mkdir()
    (base / "link").symlink_to(base / "real")

    resolved = resolve_within(base, "link/file.txt")
    assert resolved is not None
    resolved.relative_to(base.resolve())
