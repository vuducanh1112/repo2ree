from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from repo2ree_core.evidence.review.comparison import compare_source_swhids
from repo2ree_core.operations.handlers.author import acquire_source
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.operations.steps.source_repository import lay_out_run
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.lfs import LfsPointer
from repo2ree_core.source_repo import (
    LfsPayloadError,
    bundled_lfs_manifest,
    directory_swhid,
    lfs_manifest,
)
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_ree.primitives import GitRevision

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("git-lfs") is None, reason="git and git-lfs are required"
)

_PAYLOAD = b"measured\n" * 200
_LOOKALIKE = LfsPointer(oid="0" * 64, size=3).encode()


def _git(repository: Path, *args: str) -> str:
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "author",
        "GIT_AUTHOR_EMAIL": "author@localhost",
        "GIT_COMMITTER_NAME": "author",
        "GIT_COMMITTER_EMAIL": "author@localhost",
    }
    done = subprocess.run(
        ["git", "-C", str(repository), *args], check=True, capture_output=True, text=True, env=environment
    )
    return done.stdout.strip()


@pytest.fixture
def origin(tmp_path: Path) -> tuple[Path, str]:
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "--quiet", "--initial-branch=main")
    _git(origin, "lfs", "install", "--local")
    (origin / ".gitattributes").write_text("data/*.bin filter=lfs diff=lfs merge=lfs -text\nnone/*.bin filter=lfs\n")
    (origin / "data").mkdir()
    (origin / "data" / "plants.bin").write_bytes(_PAYLOAD)
    (origin / "README").write_text("an analysis\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "--quiet", "-m", "data")
    return origin, _git(origin, "rev-parse", "HEAD")


def _acquire(tmp_path: Path, origin: Path, revision: str, name: str) -> tuple[ReeLayout, str]:
    layout = ReeLayout(tmp_path / name)
    initialize_ree(layout, name="local")
    logged: list[str] = []
    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(mode="download", origin_url=f"file://{origin}", source_type="git", revision=revision),
        run_id="source",
        log=lambda _source, _level, line: logged.append(line),
        is_canceled=lambda: False,
        layout=layout,
    )
    return layout, f"{result.status}: {result.failure.message if result.failure else ''}\n" + "\n".join(logged)


def _global_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, lfs_installed: bool) -> None:
    config = tmp_path / f"gitconfig-{lfs_installed}"
    config.write_text(
        '[filter "lfs"]\n\tclean = git-lfs clean -- %f\n\tsmudge = git-lfs smudge -- %f\n'
        "\tprocess = git-lfs filter-process\n\trequired = true\n"
        if lfs_installed
        else ""
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))


@pytest.mark.parametrize("lfs_installed", [False, True], ids=["plain-git", "git-lfs-installed"])
def test_the_files_a_source_keeps_in_lfs_arrive_whatever_the_machine_configures(
    origin: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lfs_installed: bool
) -> None:
    repository, revision = origin
    _global_config(tmp_path, monkeypatch, lfs_installed=lfs_installed)

    layout, logged = _acquire(tmp_path, repository, revision, "ree")

    assert logged.startswith("succeeded"), logged
    receipt = ReeDirectory(layout).read_ree().subject.receipts.acquire_source
    assert receipt is not None
    assert [(str(file.path), file.size) for file in receipt.lfs_files] == [("data/plants.bin", len(_PAYLOAD))]
    tree = _git(repository, "rev-parse", f"{revision}^{{tree}}")
    assert receipt.observed_swhid == f"swh:1:dir:{tree}", "the identity stays the commit's tree, pointers and all"
    assert (layout.workspace / "data" / "plants.bin").read_bytes() == _PAYLOAD


def test_a_run_workspace_holds_the_lfs_files_as_git_holds_them(
    origin: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, revision = origin
    _global_config(tmp_path, monkeypatch, lfs_installed=False)
    layout, logged = _acquire(tmp_path, repository, revision, "ree")
    assert logged.startswith("succeeded"), logged

    workspace = lay_out_run(layout, ReeDirectory(layout).read_ree(), "run-1", environment=False)

    assert (workspace / "data" / "plants.bin").read_bytes() == _PAYLOAD
    assert _git(workspace, "status", "--porcelain") == ""
    (workspace / "data" / "plants.bin").unlink()
    _git(workspace, "checkout", "--", "data/plants.bin")
    assert (workspace / "data" / "plants.bin").read_bytes() == _PAYLOAD, "the content is held: no origin is asked"


def test_an_origin_without_the_lfs_content_fails_the_acquisition(
    origin: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, revision = origin
    _global_config(tmp_path, monkeypatch, lfs_installed=False)
    shutil.rmtree(repository / ".git" / "lfs" / "objects")

    layout, logged = _acquire(tmp_path, repository, revision, "ree")

    assert logged.startswith("failed"), logged
    assert ReeDirectory(layout).read_ree().subject.receipts.acquire_source is None


def test_the_manifest_takes_a_pointer_at_a_path_the_lfs_filter_holds_and_no_other(
    origin: tuple[Path, str], tmp_path: Path
) -> None:
    repository, _ = origin
    (repository / "notes").mkdir()
    (repository / "notes" / "pointer.txt").write_bytes(_LOOKALIKE)
    _git(repository, "add", "notes")
    _git(repository, "commit", "--quiet", "-m", "a pointer as a note")
    revision = _git(repository, "rev-parse", "HEAD")
    expected = {"data/plants.bin": LfsPointer(oid=hashlib.sha256(_PAYLOAD).hexdigest(), size=len(_PAYLOAD))}

    assert lfs_manifest(repository, revision) == expected
    bundle = tmp_path / "source.bundle"
    _git(repository, "update-ref", "refs/ree/source", revision)
    _git(repository, "bundle", "create", "--quiet", str(bundle), "refs/ree/source")
    assert bundled_lfs_manifest(bundle, revision=GitRevision(revision), history="full") == expected


def test_a_file_is_its_pointer_only_when_its_content_is_the_one_the_pointer_names(
    origin: tuple[Path, str], tmp_path: Path
) -> None:
    repository, revision = origin
    files = tmp_path / "files"
    shutil.copytree(repository, files, ignore=shutil.ignore_patterns(".git"))
    lfs = lfs_manifest(repository, revision)
    tree = _git(repository, "rev-parse", f"{revision}^{{tree}}")

    assert directory_swhid(files, lfs=lfs) == f"swh:1:dir:{tree}"
    (files / "data" / "plants.bin").write_bytes(lfs["data/plants.bin"].encode())
    with pytest.raises(LfsPayloadError, match="still its LFS pointer"):
        directory_swhid(files, lfs=lfs)
    (files / "data" / "plants.bin").write_bytes(_PAYLOAD[:-1] + b"?")
    with pytest.raises(LfsPayloadError, match="not the content"):
        directory_swhid(files, lfs=lfs)
    (files / "data" / "plants.bin").unlink()
    with pytest.raises(LfsPayloadError, match="missing"):
        directory_swhid(files, lfs=lfs)


def test_a_review_whose_lfs_files_did_not_arrive_finds_the_source_different() -> None:
    swhid = "swh:1:dir:" + "1" * 40
    comparison = compare_source_swhids(swhid, "", lfs_failure="data/plants.bin is still its LFS pointer")

    assert comparison.verdict == "different"
    assert comparison.lfs_failure == "data/plants.bin is still its LFS pointer"
