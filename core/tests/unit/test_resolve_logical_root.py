"""Structural coverage for ``resolve_logical_root``.

The function takes only a directory path — no acquisition kind — and peels
wrapper directories until it reaches a level that looks like a real project
root. These cases pin the decision table in the design doc.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.author_recipes.inference.repository_facts import resolve_logical_root


def _tree(root: Path, paths: list[str]) -> Path:
    for rel in paths:
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("x")
    return root


def test_flat_tree_is_its_own_root(tmp_path: Path) -> None:
    _tree(tmp_path, ["main.py", "requirements.txt"])
    assert resolve_logical_root(tmp_path) == "."


def test_single_wrapper_directory_is_peeled(tmp_path: Path) -> None:
    _tree(tmp_path, ["project-main/main.py", "project-main/README.md"])
    assert resolve_logical_root(tmp_path) == "project-main"


def test_marker_stops_descent_even_with_single_child(tmp_path: Path) -> None:
    # A real root that happens to hold one subdirectory plus a marker stops here.
    _tree(tmp_path, ["pyproject.toml", "src/pkg/__init__.py"])
    assert resolve_logical_root(tmp_path) == "."


def test_wrapper_then_marker(tmp_path: Path) -> None:
    _tree(tmp_path, ["proj-main/pyproject.toml", "proj-main/src/app.py"])
    assert resolve_logical_root(tmp_path) == "proj-main"


def test_macosx_sibling_is_ignored(tmp_path: Path) -> None:
    _tree(tmp_path, ["proj-main/main.py", "__MACOSX/._proj-main"])
    assert resolve_logical_root(tmp_path) == "proj-main"


def test_two_meaningful_top_level_entries_stay_at_root(tmp_path: Path) -> None:
    _tree(tmp_path, ["a/x.py", "b/y.py"])
    assert resolve_logical_root(tmp_path) == "."


def test_lone_top_level_file_is_not_a_wrapper(tmp_path: Path) -> None:
    _tree(tmp_path, ["only.py"])
    assert resolve_logical_root(tmp_path) == "."


def test_nested_wrapper_chain(tmp_path: Path) -> None:
    _tree(tmp_path, ["a/b/main.py"])
    assert resolve_logical_root(tmp_path) == "a/b"


def test_empty_directory_is_root(tmp_path: Path) -> None:
    assert resolve_logical_root(tmp_path) == "."
