"""What a rendered build names after its REE: the same everywhere, and its own beside other REEs."""

from __future__ import annotations

from repo2ree_core.author_recipes.inference.naming import ree_name_slug, venv_build_dir


def test_each_ree_builds_its_venv_in_a_directory_of_its_own_under_tmp() -> None:
    assert venv_build_dir("Pandas study") == "/tmp/ree-venv-pandas-study"  # noqa: S108 - the path under test
    assert venv_build_dir("Pandas study") == venv_build_dir("Pandas study")
    assert venv_build_dir("Other study") != venv_build_dir("Pandas study")
    # A name that leaves nothing to slug still names a directory.
    assert venv_build_dir("  !! ") == "/tmp/ree-venv-ree"  # noqa: S108 - the path under test


def test_the_slug_is_a_valid_docker_tag_component() -> None:
    assert ree_name_slug("My REE / v2") == "my-ree-v2"
