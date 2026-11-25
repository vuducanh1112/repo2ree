from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from repo2ree_core.source_repo import (
    SourceHistoryError,
    directory_swhid,
    lay_source_repository,
    pack_source_history,
    verify_source_history,
)
from repo2ree_ree.primitives import GitRevision, Swhid

_IDENTITY = {
    "GIT_AUTHOR_NAME": "author",
    "GIT_AUTHOR_EMAIL": "author@localhost",
    "GIT_COMMITTER_NAME": "author",
    "GIT_COMMITTER_EMAIL": "author@localhost",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repository: Path, *args: str) -> str:
    environment = {**os.environ, **_IDENTITY}
    return subprocess.run(
        ["git", "-C", str(repository), *args], check=True, capture_output=True, text=True, env=environment
    ).stdout.strip()


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "--quiet", "--initial-branch=main")
    for number in (1, 2, 3):
        (origin / "notes.txt").write_text(f"version {number}\n")
        _git(origin, "add", "notes.txt")
        _git(origin, "commit", "--quiet", "-m", f"version {number}")
        if number == 2:
            _git(origin, "tag", "-a", "v2", "-m", "release 2")
    _git(origin, "checkout", "--quiet", "-b", "side", "HEAD~2")
    (origin / "side.txt").write_text("elsewhere\n")
    _git(origin, "add", "side.txt")
    _git(origin, "commit", "--quiet", "-m", "elsewhere")
    _git(origin, "tag", "-a", "v-side", "-m", "not in main's history")
    _git(origin, "checkout", "--quiet", "main")
    _git(origin, "tag", "lightweight")
    return origin


def _clone(origin: Path, target: Path, *, shallow: bool) -> Path:
    target.mkdir()
    _git(target, "init", "--quiet")
    _git(target, "remote", "add", "origin", f"file://{origin}")
    revision = _git(origin, "rev-parse", "main")
    _git(target, "fetch", "--quiet", "--no-tags", *(["--depth", "1"] if shallow else []), "origin", revision)
    _git(target, "checkout", "--quiet", "FETCH_HEAD")
    if not shallow:
        _git(target, "fetch", "--quiet", "origin", "refs/tags/*:refs/tags/*")
    return target


def _source_of(clone: Path, target: Path) -> Swhid:
    target.mkdir()
    for path in clone.iterdir():
        if path.name != ".git":
            (target / path.name).write_bytes(path.read_bytes())
    return Swhid(directory_swhid(target))


def test_a_full_history_carries_the_ancestry_and_the_annotated_tags_in_it(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=False)
    bundle = tmp_path / "source-history.bundle"

    packed = pack_source_history(clone, bundle)

    assert packed.history == "full"
    assert packed.revision == _git(origin, "rev-parse", "main")
    heads = _git(tmp_path, "bundle", "list-heads", str(bundle))
    assert "refs/ree/source" in heads
    assert "refs/tags/v2" in heads
    assert "refs/tags/v-side" not in heads
    assert "refs/tags/lightweight" not in heads


def test_a_shallow_clone_packs_the_commit_alone(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=True)

    packed = pack_source_history(clone, tmp_path / "source-history.bundle")

    assert packed.history == "tip"


@pytest.mark.parametrize("shallow", [False, True])
def test_a_packed_history_verifies_against_its_commit_and_tree(origin: Path, tmp_path: Path, shallow: bool) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=shallow)
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)

    verify_source_history(
        bundle, revision=packed.revision, swhid=_source_of(clone, tmp_path / "files"), history=packed.history
    )


def test_a_history_of_another_commit_is_refused(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=False)
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)
    other = GitRevision(_git(origin, "rev-parse", "main~1"))

    with pytest.raises(SourceHistoryError, match="holds commit"):
        verify_source_history(
            bundle, revision=other, swhid=_source_of(clone, tmp_path / "files"), history=packed.history
        )


def test_a_history_whose_commit_holds_other_files_is_refused(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=False)
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)
    other = tmp_path / "other"
    other.mkdir()
    (other / "notes.txt").write_text("something else\n")

    with pytest.raises(SourceHistoryError, match="holds tree"):
        verify_source_history(
            bundle, revision=packed.revision, swhid=Swhid(directory_swhid(other)), history=packed.history
        )


def test_a_history_is_refused_when_it_is_not_as_deep_as_recorded(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=True)
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)

    with pytest.raises(SourceHistoryError):
        verify_source_history(
            bundle, revision=packed.revision, swhid=_source_of(clone, tmp_path / "files"), history="full"
        )


def test_a_damaged_history_is_refused(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=False)
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)
    damaged = bytearray(bundle.read_bytes())
    damaged[-40] ^= 0xFF
    bundle.write_bytes(bytes(damaged))

    with pytest.raises(SourceHistoryError):
        verify_source_history(
            bundle, revision=packed.revision, swhid=_source_of(clone, tmp_path / "files"), history=packed.history
        )


@pytest.mark.parametrize("shallow", [False, True])
def test_a_workspace_gets_the_commit_and_nothing_of_the_clone(origin: Path, tmp_path: Path, shallow: bool) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=shallow)
    (clone / ".git" / "hooks" / "post-checkout").write_text("#!/bin/sh\nexit 1\n")
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)
    workspace = tmp_path / "workspace"
    _source_of(clone, workspace)
    (workspace / "ree-scripts").mkdir()
    (workspace / "ree-scripts" / "run.sh").write_text("true\n")

    lay_source_repository(
        workspace, bundle, revision=packed.revision, history=packed.history, left_out=("/ree-scripts/",)
    )

    assert _git(workspace, "rev-parse", "HEAD") == packed.revision
    assert _git(workspace, "status", "--porcelain") == ""
    assert _git(workspace, "remote") == ""
    assert not (workspace / ".git" / "hooks" / "post-checkout").exists()
    assert _git(workspace, "config", "core.hooksPath").endswith("ree-no-hooks")
    if shallow:
        assert _git(workspace, "rev-parse", "--is-shallow-repository") == "true"
    else:
        assert _git(workspace, "rev-list", "--count", "HEAD") == "3"
        assert _git(workspace, "describe", "--tags") == "v2-1-g" + packed.revision[:7]


def test_two_workspaces_of_one_history_hold_the_same_repository(origin: Path, tmp_path: Path) -> None:
    clone = _clone(origin, tmp_path / "clone", shallow=False)
    bundle = tmp_path / "source-history.bundle"
    packed = pack_source_history(clone, bundle)

    def laid(name: str) -> tuple[str, str, str]:
        workspace = tmp_path / name
        _source_of(clone, workspace)
        lay_source_repository(workspace, bundle, revision=packed.revision, history=packed.history, left_out=())
        objects = _git(workspace, "rev-list", "--objects", "--all")
        return _git(workspace, "rev-parse", "HEAD"), _git(workspace, "show-ref"), objects

    assert laid("author") == laid("reviewer")
