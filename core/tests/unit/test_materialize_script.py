"""Tests for the generated ``materialize_workspace.sh`` (the merge muscle)."""

import subprocess
from pathlib import Path

from repo2ree_core.authoring.script_generation.materialize_workspace import build_materialize_sh
from repo2ree_core.persistence.layout import (
    MATERIALIZE_SCRIPT_FILENAME,
    OVERLAY_DIRNAME,
    UPSTREAM_DIRNAME,
    WORKSPACE_DIRNAME,
)


def _run(tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    path = tmp / MATERIALIZE_SCRIPT_FILENAME
    path.write_bytes(build_materialize_sh())
    return subprocess.run(["sh", str(path), *args], text=True, capture_output=True)


def test_generated_materialize_sh_is_valid_posix():
    script = build_materialize_sh()
    assert script.startswith(b"#!/bin/sh")
    assert b"@@" not in script
    result = subprocess.run(["sh", "-n", "/dev/stdin"], input=script, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_materialize_sh_is_deterministic():
    assert build_materialize_sh() == build_materialize_sh()


def test_merges_upstream_then_overlay_with_overlay_winning(tmp_path):
    upstream = tmp_path / UPSTREAM_DIRNAME
    overlay = tmp_path / OVERLAY_DIRNAME
    (upstream / "sub").mkdir(parents=True)
    (upstream / "keep.txt").write_text("from upstream\n")
    (upstream / "shared.txt").write_text("upstream loses\n")
    (upstream / "sub" / "nested.txt").write_text("nested\n")
    overlay.mkdir()
    (overlay / "shared.txt").write_text("overlay wins\n")
    (overlay / "build.sh").write_text("#!/bin/sh\n")

    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr

    ws = tmp_path / WORKSPACE_DIRNAME
    assert (ws / "keep.txt").read_text() == "from upstream\n"
    assert (ws / "sub" / "nested.txt").read_text() == "nested\n"
    assert (ws / "shared.txt").read_text() == "overlay wins\n"  # overlay wins on conflict
    assert (ws / "build.sh").is_file()


def test_clears_stray_workspace_state_before_merge(tmp_path):
    (tmp_path / UPSTREAM_DIRNAME).mkdir()
    (tmp_path / UPSTREAM_DIRNAME / "keep.txt").write_text("kept\n")
    ws = tmp_path / WORKSPACE_DIRNAME
    ws.mkdir()
    stray = ws / "stray.txt"
    stray.write_text("left over\n")

    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert not stray.exists()  # clean slate
    assert (ws / "keep.txt").read_text() == "kept\n"


def test_overlay_only_when_upstream_empty(tmp_path):
    # No upstream dir at all (overlay-only source): not an error.
    overlay = tmp_path / OVERLAY_DIRNAME
    overlay.mkdir()
    (overlay / "run.sh").write_text("#!/bin/sh\n")

    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / WORKSPACE_DIRNAME / "run.sh").is_file()


def test_usage_error_on_extra_arg(tmp_path):
    result = _run(tmp_path, "unexpected")
    assert result.returncode == 2
    assert "usage" in result.stderr
