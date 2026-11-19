"""The command line: each command does what it says, from the specification on disk."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from repo2ree_assurance_checker.cli import main
from repo2ree_assurance_checker.export import FORMAT
from repo2ree_assurance_checker.files import load_spec


def test_describe_prints_the_digests_and_every_invariant(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["describe"]) == 0
    printed, spec = capsys.readouterr().out, load_spec()
    assert printed.startswith(f"{spec.digest}\n  vocabulary {spec.vocabulary_digest}\n")
    assert all(f"  invariant {invariant.id} ({invariant.pattern})" in printed for invariant in spec.invariants)


def test_export_writes_the_specification_as_versioned_json(tmp_path: Path) -> None:
    target = tmp_path / "spec.json"
    assert main(["export", "-o", str(target)]) == 0
    exported = json.loads(target.read_text())
    assert (exported["format"], exported["digest"]) == (FORMAT, load_spec().digest)


def test_map_draws_every_component(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["map"]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("flowchart LR")
    assert all(f"component_{name}" in printed for name in load_spec().components)


def test_a_diff_against_the_committed_specification_says_what_changed(tmp_path: Path) -> None:
    # The working tree's specification as a commit of its own, so the base is one this checker reads even while
    # its format changes. A separate index leaves the repository's own, and whatever it holds, alone.
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp_path / "index")}

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True, env=env).stdout.strip()

    git("read-tree", "HEAD")
    git("add", "--", "assurance/spec")
    base = git("commit-tree", git("write-tree"), "-p", "HEAD", "-m", "the working tree's specification")
    target = tmp_path / "diff.md"
    assert main(["diff", "--base", base, "-o", str(target)]) == 0
    rendered = target.read_text()
    assert rendered.startswith("# Behaviour specification change")
    assert load_spec().digest in rendered


def test_check_refuses_what_is_not_a_dossier(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "--dossier", str(tmp_path)]) == 2
    assert "not a dossier" in capsys.readouterr().err


def test_validate_journal_needs_journal_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate-journal", str(tmp_path)]) == 1
    assert "no journal files" in capsys.readouterr().err
