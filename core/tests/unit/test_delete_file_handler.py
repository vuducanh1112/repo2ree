"""Unit coverage for the delete_file envelope handler.

The handler runs inside the workbench against the fixed ``/ree`` layout; these
tests point ``ReeLayout.in_workbench`` at a tmp root (the same seam the other
handler tests use) and exercise the three outcomes: restore-from-upstream,
remove-entirely, and the guard paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.envelope.handlers import delete_file as handler
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_protocol.command import DeleteFileArgs


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


def _store_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeStore:
    store = ReeStore(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    monkeypatch.setattr(handler.ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return store


def test_canceled_before_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    result = handler.handle_delete_file(DeleteFileArgs(path="a.txt"), log=_silent_log, is_canceled=lambda: True)
    assert result.status == "canceled"


def test_invalid_path_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    result = handler.handle_delete_file(DeleteFileArgs(path="../escape"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "failed"
    assert result.exit_code == 1


def test_missing_file_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    result = handler.handle_delete_file(DeleteFileArgs(path="ghost.txt"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "failed"


def test_upstream_file_is_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store_at(tmp_path, monkeypatch)
    # A file that exists upstream and was overridden in the overlay: deleting the
    # override restores the upstream content into the workspace.
    store.upstream.write_bytes("readme.md", b"upstream body")
    store.overlay.write_bytes("readme.md", b"local edit")
    store.workspace.write_bytes("readme.md", b"local edit")

    result = handler.handle_delete_file(DeleteFileArgs(path="readme.md"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "succeeded"
    assert not store.overlay.is_file("readme.md")
    assert store.workspace.read_bytes("readme.md") == b"upstream body"


def test_overlay_only_file_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store_at(tmp_path, monkeypatch)
    # A file created purely in the overlay (no upstream origin): deleting it
    # removes it from the workspace entirely.
    store.overlay.write_bytes("new.txt", b"created here")
    store.workspace.write_bytes("new.txt", b"created here")

    result = handler.handle_delete_file(DeleteFileArgs(path="new.txt"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "succeeded"
    assert not store.workspace.is_file("new.txt")
    assert not store.overlay.is_file("new.txt")
