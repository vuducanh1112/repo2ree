"""A CLI session is drawn as each command with the REE as it left it, from the client's session and the REE's
history."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest

from repo2ree_testbed.cli_session import SESSION, CliCommand, append, kept_result, kept_stdin, read_session
from repo2ree_testbed.runs import session

pytestmark = pytest.mark.skipif(shutil.which("ree") is None, reason="needs the ree command line")


def run(test: Path, root: Path, run_id: str, *words: str, stdin: bytes | None = None) -> None:
    """Run ``ree`` as the CLI showcase client does, and write it down in the test's session."""
    started = time.time()
    done = subprocess.run(
        ["ree", "-C", str(root), "--json", "--run-id", run_id, *words], input=stdin, capture_output=True, check=False
    )
    result, size = kept_result(done.stdout.decode().strip().splitlines()[-1])
    text, stdin_bytes = kept_stdin(stdin)
    command = CliCommand(
        ree=root.name,
        words=words,
        run_id=run_id,
        stdin=text,
        stdin_bytes=stdin_bytes,
        exit=done.returncode,
        result=result,
        result_bytes=size,
        started=started,
        finished=time.time(),
    )
    append(test / "artifacts" / SESSION, command)


@pytest.fixture
def test_dir(tmp_path: Path) -> Path:
    test = tmp_path / "test"
    root = tmp_path / "work" / "demo-1"
    run(test, root, "run-1", "initialize-ree", "--name", "demo")
    run(test, root, "run-2", "write-script", "build_experiment_environment", stdin=b"echo built\n")
    run(test, root, "run-3", "patch-ree-definition", "--version", "1.0")
    run(test, root, "run-4", "status")
    shutil.copytree(root / ".git", test / "dossier/rees/demo-1/ree/.git")
    return test


def test_each_command_is_shown_with_the_commits_its_run_made(test_dir: Path) -> None:
    found, unmatched = session.steps(read_session(test_dir / "artifacts" / SESSION), test_dir / "dossier")

    assert [step.command.words[0] for step in found] == [
        "initialize-ree",
        "write-script",
        "patch-ree-definition",
        "status",
    ]
    assert [[change.commit.operation for change in step.changes] for step in found] == [
        ["initialize_ree"],
        ["write_script"],
        ["patch_ree_definition"],
        [],
    ]
    assert unmatched == []


def test_a_change_names_the_files_and_the_document_values_it_changed(test_dir: Path) -> None:
    found, _ = session.steps(read_session(test_dir / "artifacts" / SESSION), test_dir / "dossier")
    [written] = found[1].changes
    [defined] = found[2].changes

    assert "overlay/ree-scripts/build_experiment_environment.sh" in written.changed
    assert any(path == "subject.definition.catalog.version" for path, _, _ in defined.fields)
    assert ("subject.definition.catalog.version", '""', '"1.0"') in defined.fields
    assert defined.commit.document_path == "ree.json"


def test_the_page_shows_each_command_and_a_read_as_one_line(test_dir: Path, tmp_path: Path) -> None:
    assert session.draw(test_dir, tmp_path / "report", "a test")

    page = (tmp_path / "report/index.html").read_text()
    assert "$ ree write-script build_experiment_environment" in page
    assert "read, changed nothing" in page
    assert "the file tree after it" in page


def test_a_test_that_left_no_session_draws_none(tmp_path: Path) -> None:
    assert not session.draw(tmp_path, tmp_path / "report", "a test")


def test_the_page_says_where_its_evidence_came_from_and_plays_its_video(test_dir: Path, tmp_path: Path) -> None:
    about = [("Recorded", "run showcase-cli-1 of abcdef1234"), ("Drawn by", "fedcba9876 + uncommitted changes")]
    video = tmp_path / "sessions/showcase-cli-1/the-test.mp4"
    report = tmp_path / "behaviour/showcase-cli-1/tests/the-test/session"

    assert session.draw(test_dir, report, "a test", about=about, video=video)
    unrendered = (report / "index.html").read_text()
    video.parent.mkdir(parents=True)
    video.write_bytes(b"mp4")
    assert session.draw(test_dir, report, "a test", about=about, video=video)
    page = (report / "index.html").read_text()

    assert "<th>Recorded</th><td>run showcase-cli-1 of abcdef1234</td>" in page
    assert "<th>Drawn by</th><td>fedcba9876 + uncommitted changes</td>" in page
    assert "<video" not in unrendered, "no player for a video not rendered"
    assert "src='../../../../../sessions/showcase-cli-1/the-test.mp4'" in page
