"""Initialization owns its first version, including retries after capture failure."""

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.read_models.files import list_ree_files, list_workspace_files, read_ree_file_bytes
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.tooling import find_tool


def git(layout: ReeLayout, *args: str) -> bytes:
    executable = find_tool("git")
    assert executable is not None, "initialization tests require Git"
    return subprocess.run(
        [executable, "--git-dir", str(layout.git_dir), "--work-tree", str(layout.root), *args],
        env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
        check=True,
        capture_output=True,
    ).stdout


def test_initial_snapshot_contains_the_actual_ree_and_scripts(tmp_path):
    layout = ReeLayout.for_ree(tmp_path, "ree")
    result = initialize_ree(layout, name="demo")
    assert result.status == "initialised"
    assert git(layout, "show", f"{result.snapshot_id}:ree.json") == layout.manifest.read_bytes()
    assert json.loads(layout.manifest.read_bytes())["subject"]["definition"]["name"] == "demo"
    for tree in ("overlay",):
        path = f"{tree}/{RESERVED_BUILD_SCRIPT}"
        assert git(layout, "show", f"{result.snapshot_id}:{path}") == (layout.root / path).read_bytes()
    assert git(layout, "log", "-1", "--format=%s").strip() == b"initialize_ree"
    assert git(layout, "rev-list", "--count", "HEAD").strip() == b"1"
    assert layout.upstream.is_dir()
    assert layout.artifacts.is_dir()


def test_repeat_preserves_authored_files_and_returns_original_snapshot(tmp_path):
    layout = ReeLayout.for_ree(tmp_path, "ree")
    first = initialize_ree(layout, name="demo")
    original = layout.overlay_file(RESERVED_BUILD_SCRIPT).read_bytes()
    layout.overlay_file(RESERVED_BUILD_SCRIPT).write_bytes(b"changed after initialization")
    second = initialize_ree(layout, name="different name")
    assert second.status == "already_initialised"
    assert second.snapshot_id == first.snapshot_id
    assert json.loads(layout.manifest.read_bytes())["subject"]["definition"]["name"] == "demo"
    assert layout.overlay_file(RESERVED_BUILD_SCRIPT).read_bytes() == b"changed after initialization"
    assert git(layout, "show", f"{first.snapshot_id}:overlay/{RESERVED_BUILD_SCRIPT}") == original
    assert git(layout, "rev-list", "--count", "HEAD").strip() == b"1"


def test_git_ignores_filters_and_callers_repository_do_not_change_capture(tmp_path, monkeypatch):
    layout = ReeLayout.for_ree(tmp_path, "ree")
    layout.root.mkdir()
    layout.overlay.mkdir()
    (layout.overlay / ".gitignore").write_text("*\n")
    (layout.overlay / ".gitattributes").write_text("* text eol=lf\n")
    (layout.overlay / "bytes.txt").write_bytes(b"keep\r\nthese\r\nbytes\x00")
    executable = layout.overlay / "executable.sh"
    executable.write_bytes(b"#!/bin/sh\n")
    executable.chmod(0o755)
    (layout.overlay / "link").symlink_to("bytes.txt")
    foreign = tmp_path / "foreign.git"
    monkeypatch.setenv("GIT_DIR", str(foreign))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "foreign-index"))
    result = initialize_ree(layout, name="demo")
    assert not foreign.exists()
    assert not (tmp_path / "foreign-index").exists()
    assert git(layout, "show", f"{result.snapshot_id}:overlay/bytes.txt") == (layout.overlay / "bytes.txt").read_bytes()
    assert git(layout, "show", f"{result.snapshot_id}:overlay/link") == b"bytes.txt"
    assert git(layout, "ls-tree", result.snapshot_id, "overlay/executable.sh").startswith(b"100755 blob")


def test_failed_capture_can_be_retried_without_overwriting_ree(tmp_path, monkeypatch):
    layout = ReeLayout.for_ree(tmp_path, "ree")

    def fail_capture(self, *, operation):
        raise HistoryCaptureError("injected capture failure")

    with monkeypatch.context() as patch:
        patch.setattr(GitHistory, "capture", fail_capture)
        with pytest.raises(HistoryCaptureError, match="injected capture failure"):
            initialize_ree(layout, name="demo")
    before = layout.manifest.read_bytes()
    result = initialize_ree(layout, name="must not overwrite")
    assert result.status == "already_initialised"
    assert layout.manifest.read_bytes() == before
    assert git(layout, "show", f"{result.snapshot_id}:ree.json") == before
    assert git(layout, "log", "-1", "--format=%s").strip() == b"baseline_existing_ree"


def test_missing_git_fails_before_creating_ree(tmp_path, monkeypatch):
    layout = ReeLayout.for_ree(tmp_path, "ree")
    monkeypatch.setattr("repo2ree_core.persistence.history.find_tool", lambda name: None)
    with pytest.raises(HistoryCaptureError, match="Git is required"):
        initialize_ree(layout, name="demo")
    assert not layout.root.exists()


def test_unreadable_directory_does_not_publish_an_incomplete_snapshot(tmp_path, monkeypatch):
    layout = ReeLayout.for_ree(tmp_path, "ree")

    def unreadable_walk(self, *, on_error=None):
        assert on_error is not None, "capture must handle directory traversal errors"
        on_error(PermissionError("unreadable directory"))
        return iter(())

    with monkeypatch.context() as patch:
        patch.setattr(Path, "walk", unreadable_walk)
        with pytest.raises(HistoryCaptureError, match="unreadable directory"):
            initialize_ree(layout, name="demo")
    assert git(layout, "for-each-ref", "refs/repo2ree/initial") == b""
    assert initialize_ree(layout, name="demo").snapshot_id


def test_parallel_initialization_creates_one_baseline(tmp_path):
    layout = ReeLayout.for_ree(tmp_path, "ree")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: initialize_ree(layout, name="demo"), range(2)))
    assert {result.status for result in results} == {"initialised", "already_initialised"}
    assert len({result.snapshot_id for result in results}) == 1
    assert git(layout, "rev-list", "--count", "HEAD").strip() == b"1"


def test_git_storage_is_not_a_visible_file_or_bundle_content(tmp_path):
    layout = ReeLayout.for_ree(tmp_path, "ree")
    initialize_ree(layout, name="demo")
    assert not any(entry.path.startswith(".git/") for entry in list_ree_files(layout))
    with pytest.raises(ValueError, match="Invalid REE file path"):
        read_ree_file_bytes(layout, ".git/config")
    with materialized_ree_download(layout) as archive_path, zipfile.ZipFile(archive_path) as archive:
        assert "ree/.git/HEAD" in archive.namelist()
    # A symlink must not make private repository bytes visible through another path.
    (layout.workspace / "git-config").symlink_to(layout.git_dir / "config")
    assert not any(entry.path == "git-config" for entry in list_workspace_files(layout))
    with pytest.raises(ValueError, match="Invalid REE file path"):
        read_ree_file_bytes(layout, "workspace/git-config")
