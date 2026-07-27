from pathlib import PurePosixPath

import pytest

from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore


def _store(tmp_path) -> ReeStore:
    return ReeStore(ReeLayout.for_ree(tmp_path, "ree-1"))


def test_ensure_dirs_creates_all_subtrees(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    assert store.layout.upstream.is_dir()
    assert store.layout.overlay.is_dir()
    assert store.layout.artifacts.is_dir()
    assert store.layout.workspace.is_dir()
    assert store.layout.upload_staging.is_dir()


def test_overlay_write_and_read_text(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("Dockerfile", "FROM scratch\n")
    assert store.overlay.read_text("Dockerfile") == "FROM scratch\n"
    assert store.overlay.is_file("Dockerfile")


def test_overlay_write_creates_intermediate_dirs(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("nix/flakes/flake.nix", "{}")
    assert store.overlay.is_file("nix/flakes/flake.nix")


def test_artifacts_write_and_read_bytes(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    payload = b"\x00\x01\x02tarball\xff"
    store.artifacts.write_bytes("runtime.tar.gz", payload)
    assert store.artifacts.read_bytes("runtime.tar.gz") == payload


def test_three_subtrees_are_isolated(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.upstream.write_text("file.txt", "upstream")
    store.overlay.write_text("file.txt", "overlay")
    store.artifacts.write_text("file.txt", "artifact")

    assert store.upstream.read_text("file.txt") == "upstream"
    assert store.overlay.read_text("file.txt") == "overlay"
    assert store.artifacts.read_text("file.txt") == "artifact"


def test_delete_removes_file(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("scratch", "x")
    store.overlay.delete("scratch")
    assert not store.overlay.exists("scratch")


def test_delete_raises_when_missing(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    with pytest.raises(FileNotFoundError):
        store.overlay.delete("never-existed")


def test_delete_if_exists_returns_bool(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("scratch", "x")
    assert store.overlay.delete_if_exists("scratch") is True
    assert store.overlay.delete_if_exists("scratch") is False


def test_delete_removes_directory_recursively(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("dir/a.txt", "a")
    store.overlay.write_text("dir/b.txt", "b")
    store.overlay.delete("dir")
    assert not store.overlay.exists("dir")


def test_clear_empties_subtree_but_keeps_root(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("a", "1")
    store.overlay.write_text("nested/b", "2")
    store.overlay.clear()
    assert store.layout.overlay.is_dir()
    assert store.overlay.list_files() == []


def test_iter_files_returns_posix_relative_paths(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("Dockerfile", "")
    store.overlay.write_text("nix/flake.nix", "")
    store.overlay.write_text("a/b/c.txt", "")

    files = store.overlay.list_files()
    assert files == [
        PurePosixPath("Dockerfile"),
        PurePosixPath("a/b/c.txt"),
        PurePosixPath("nix/flake.nix"),
    ]


def test_iter_files_on_missing_root_is_empty(tmp_path):
    store = _store(tmp_path)
    # do not ensure_dirs — overlay root does not exist
    assert store.overlay.list_files() == []


def test_absolute_rejects_unsafe_paths(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    with pytest.raises(ValueError):
        store.overlay.absolute("../escape")
    with pytest.raises(ValueError):
        store.overlay.absolute("/etc/passwd")


def test_write_rejects_unsafe_paths(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    with pytest.raises(ValueError):
        store.overlay.write_text("../escape", "x")


def test_ensure_dirs_is_idempotent_for_subtrees(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.overlay.write_text("keep", "1")
    store.ensure_dirs()
    assert store.overlay.read_text("keep") == "1"
