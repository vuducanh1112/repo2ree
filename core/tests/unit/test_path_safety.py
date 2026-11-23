from __future__ import annotations

from pathlib import Path

from repo2ree_ree.paths import resolve_within


def test_symlink_escaping_base_is_rejected(tmp_path: Path) -> None:
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
