"""The example REE is staged from the newest showcase run that sealed it, and adopted only if it holds the spec."""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest
from scripts import example_bundle


def sealed(runs: Path, run: str, name: str, *, age: int) -> Path:
    archives = runs / run / "tests" / f"{example_bundle.TEST}test-provision" / "artifacts" / "archives"
    archives.mkdir(parents=True)
    bundle = archives / f"sealed-{run}.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("ree/ree.json", json.dumps({"subject": {"definition": {"name": name}}}))
    os.utime(bundle, (age, age))
    return bundle


def test_the_newest_command_line_run_is_staged(tmp_path: Path) -> None:
    runs = tmp_path / "e2e"
    sealed(runs, "showcase-cli-1", example_bundle.NAME, age=1)
    newest = sealed(runs, "showcase-cli-2", example_bundle.NAME, age=2)
    sealed(runs, "showcase-api-3", example_bundle.NAME, age=3)
    staged = example_bundle.stage(runs, tmp_path / "staged.zip")
    assert staged.read_bytes() == newest.read_bytes()


def test_a_bundle_of_another_ree_is_never_staged(tmp_path: Path) -> None:
    runs = tmp_path / "e2e"
    sealed(runs, "showcase-cli-1", "something-else", age=1)
    with pytest.raises(SystemExit, match="not 'ree-hello-world'"):
        example_bundle.stage(runs, tmp_path / "staged.zip")
    with pytest.raises(SystemExit, match="sealed the Python Docker REE"):
        example_bundle.stage(tmp_path / "nothing", tmp_path / "staged.zip")


def test_a_bundle_is_adopted_only_if_it_holds_the_specification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged, example = tmp_path / "staged.zip", tmp_path / "example.zip"
    staged.write_bytes(b"new")
    example.write_bytes(b"old")
    monkeypatch.setattr(example_bundle, "check", lambda bundle: ["aggregate:Ree judged nothing"])
    with pytest.raises(SystemExit, match="the example is unchanged"):
        example_bundle.adopt(staged, example)
    assert example.read_bytes() == b"old"
    monkeypatch.setattr(example_bundle, "check", lambda bundle: [])
    example_bundle.adopt(staged, example)
    assert example.read_bytes() == b"new"


GIT = shutil.which("git")


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_the_example_holds_every_rule_on_the_ree_document() -> None:
    assert example_bundle.check(example_bundle.EXAMPLE) == []


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_a_bundle_whose_history_holds_no_ree_judges_nothing_and_is_refused(tmp_path: Path) -> None:
    bundle = tmp_path / "empty.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("ree/ree.json", "{}")
    assert any("judged nothing" in problem for problem in example_bundle.check(bundle))
