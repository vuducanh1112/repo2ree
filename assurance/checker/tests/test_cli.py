"""The command line: each command does what it says, from the specification on disk."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_assurance_checker.cli import main
from repo2ree_assurance_checker.export import FORMAT
from repo2ree_assurance_checker.files import GENERATED_SCHEMA, load_spec


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
    target = tmp_path / "diff.md"
    assert main(["diff", "--base", "HEAD", "-o", str(target)]) == 0
    rendered = target.read_text()
    assert rendered.startswith("# Behaviour specification change")
    assert load_spec().digest in rendered


def test_generate_writes_the_published_schema_and_check_refuses_a_stale_one(tmp_path: Path) -> None:
    target = tmp_path / "events.schema.json"
    assert main(["generate", "--check", "--output", str(target)]) == 1  # Not written yet: stale.
    assert main(["generate", "--output", str(target)]) == 0
    assert target.read_text() == GENERATED_SCHEMA.read_text()
    assert main(["generate", "--check", "--output", str(target)]) == 0


def test_check_refuses_what_is_not_a_dossier(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "--dossier", str(tmp_path)]) == 2
    assert "not a dossier" in capsys.readouterr().err


def test_validate_journal_needs_journal_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate-journal", str(tmp_path)]) == 1
    assert "no journal files" in capsys.readouterr().err
