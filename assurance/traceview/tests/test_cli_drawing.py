from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repo2ree_assurance_traceview.cli import drawing

GIT = shutil.which("git")


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_the_drawing_commit_is_the_checkout_s_and_says_when_it_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert GIT is not None
    monkeypatch.chdir(tmp_path)
    for command in (
        ["init", "-q"],
        ["-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "--allow-empty", "-m", "c"],
    ):
        subprocess.run([GIT, *command], check=True)
    head = subprocess.run([GIT, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    clean = drawing(GIT)
    (tmp_path / "changed.txt").write_text("x")
    dirty = drawing(GIT)

    assert clean is not None
    assert dirty is not None
    assert (clean.revision, clean.dirty) == (head, False)
    assert dirty.dirty
    monkeypatch.chdir(tmp_path.parent)
    assert drawing(str(tmp_path / "no-git-here")) is None
