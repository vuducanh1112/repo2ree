from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repo2ree_core.source_repo import content_swhid, directory_swhid


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class TestContentSwhid:
    def test_matches_git_blob_hash(self) -> None:
        # echo -n is awkward across shells; git hash-object of "hello\n".
        assert content_swhid(b"hello\n") == "swh:1:cnt:ce013625030ba8dba906f756967f9e9ca394464a"

    def test_empty_content(self) -> None:
        assert content_swhid(b"") == "swh:1:cnt:e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


class TestDirectorySwhid:
    def test_rejects_non_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope"
        with pytest.raises(NotADirectoryError):
            directory_swhid(missing)

    def test_matches_git_write_tree(self, tmp_path: Path) -> None:
        """The directory SWHID is git's tree hash of an equivalent checkout."""
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").write_bytes(b"hello\n")
        (tmp_path / "sub" / "b.txt").write_bytes(b"world\n")
        run = tmp_path / "run.sh"
        run.write_bytes(b"#!/bin/sh\necho hi\n")
        run.chmod(0o755)
        (tmp_path / "link.txt").symlink_to("a.txt")

        _git(tmp_path, "init", "-q")
        _git(tmp_path, "add", "-A")
        expected = _git(tmp_path, "write-tree")

        assert directory_swhid(tmp_path) == f"swh:1:dir:{expected}"

    def test_excludes_git_directory(self, tmp_path: Path) -> None:
        """A ``.git`` dir must not change the identifier of the source."""
        (tmp_path / "a.txt").write_bytes(b"hello\n")
        before = directory_swhid(tmp_path)

        _git(tmp_path, "init", "-q")  # creates .git/
        assert directory_swhid(tmp_path) == before

    @pytest.mark.skipif(
        shutil.which("swh") is None,
        reason="official Software Heritage CLI (swh.model) not installed",
    )
    def test_matches_official_swh_identify(self, tmp_path: Path) -> None:
        """Cross-check against ``swh identify`` whenever the official tool is present.

        Validates our reimplementation against Software Heritage's own
        implementation without taking ``swh.model`` as a hard dependency.
        """
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").write_bytes(b"hello\n")
        (tmp_path / "sub" / "b.txt").write_bytes(b"world\n")

        official = subprocess.run(
            ["swh", "identify", "--type", "directory", str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()[0]

        assert directory_swhid(tmp_path) == official
