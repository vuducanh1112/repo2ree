"""Tests for the generated ``acquire_source.sh`` (``acquire_script``)."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from repo2ree_core.authoring.script_generation.acquire_source import build_acquire_sh
from repo2ree_core.ree.layout import ACQUIRE_SCRIPT_FILENAME, SNAPSHOT_FILENAME, UPSTREAM_DIRNAME


def _sh_n(script: bytes) -> subprocess.CompletedProcess[bytes]:
    """Syntax-check a generated script with ``sh -n`` (no execution)."""
    return subprocess.run(["sh", "-n", "/dev/stdin"], input=script, capture_output=True)


def _run(script: bytes, tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    path = tmp / ACQUIRE_SCRIPT_FILENAME
    path.write_bytes(script)
    return subprocess.run(["sh", str(path), *args], text=True, capture_output=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # upload: no origin/type/swhid
        {"origin_url": "https://example.com/r.git", "source_type": "git"},
        {"origin_url": "https://example.com/s.tgz", "source_type": "tarball", "swhid": "swh:1:dir:abc"},
    ],
)
def test_generated_acquire_sh_is_valid_posix(kwargs):
    script = build_acquire_sh(**kwargs)
    assert script.startswith(b"#!/bin/sh")
    result = _sh_n(script)
    assert result.returncode == 0, result.stderr


def test_acquire_sh_is_deterministic_for_equal_inputs():
    kwargs = {"origin_url": "https://example.com/repo.git", "source_type": "git", "swhid": "swh:1:dir:x"}
    assert build_acquire_sh(**kwargs) == build_acquire_sh(**kwargs)


def test_bakes_origin_swhid_and_only_the_relevant_fetch_command():
    script = build_acquire_sh(origin_url="https://e/r.git", source_type="git", swhid="swh:1:dir:z").decode()
    assert "ORIGIN_URL='https://e/r.git'" in script
    assert "SWHID='swh:1:dir:z'" in script
    assert "@@" not in script
    assert 'case "$SOURCE_TYPE"' not in script
    assert "git clone --depth 1" in script
    assert "unzip -q" not in script


def test_bakes_git_revision_and_pins_the_fetch():
    script = build_acquire_sh(origin_url="https://e/r.git", source_type="git", revision="deadbeef").decode()
    assert "rev='deadbeef'" in script
    # The pinned variant fetches the specific commit instead of cloning HEAD.
    assert "fetch -q --depth 1 origin" in script
    assert "git clone --depth 1" not in script


def test_fetches_recorded_git_revision_when_snapshot_missing(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to exercise the generated git fetch command")

    origin = tmp_path / "origin"
    origin.mkdir()
    git = ["git", "-C", str(origin), "-c", "user.name=t", "-c", "user.email=t@e"]
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    (origin / "v.txt").write_text("first\n")
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "first"], check=True)
    pinned = subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    # Advance the branch so an unpinned clone of HEAD would get the wrong tree.
    (origin / "v.txt").write_text("second\n")
    subprocess.run([*git, "commit", "-qa", "-m", "second"], check=True)

    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(build_acquire_sh(origin_url=str(origin), source_type="git", revision=pinned), tmp_path)
    assert result.returncode == 0, result.stderr
    assert (upstream / "v.txt").read_text() == "first\n"


def test_extracts_snapshot_when_present(tmp_path):
    # Build a snapshot tar.gz with one file, then acquire from it (no origin).
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("hi\n")
    subprocess.run(["tar", "-czf", str(tmp_path / SNAPSHOT_FILENAME), "-C", str(src), "."], check=True)

    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(build_acquire_sh(), tmp_path)
    assert result.returncode == 0, result.stderr
    assert (upstream / "hello.txt").read_text() == "hi\n"


def test_idempotent_skip_when_upstream_populated(tmp_path):
    upstream = tmp_path / UPSTREAM_DIRNAME
    upstream.mkdir()
    (upstream / "keep.txt").write_text("kept\n")
    # No snapshot, no origin: would normally die — but populated upstream skips.
    result = _run(build_acquire_sh(), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "already populated" in result.stdout
    assert (upstream / "keep.txt").exists()


def test_overlay_only_when_no_snapshot_or_origin(tmp_path):
    # No snapshot and no origin: not an error — upstream is left empty so an
    # overlay-only bundle still reproduces.
    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(build_acquire_sh(), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "overlay-only" in result.stdout
    assert upstream.is_dir()
    assert not any(upstream.iterdir())


def test_fetches_local_tarball_origin_when_snapshot_missing(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('tarball')\n")
    archive = tmp_path / "source.tar.gz"
    subprocess.run(["tar", "-czf", str(archive), "-C", str(src), "."], check=True)

    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(
        build_acquire_sh(origin_url=str(archive), source_type="tarball"),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (upstream / "main.py").read_text() == "print('tarball')\n"


def test_fetches_local_zip_origin_when_snapshot_missing(tmp_path):
    if shutil.which("unzip") is None:
        pytest.skip("unzip is required to exercise the generated zip fetch command")

    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("main.py", "print('zip')\n")

    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(
        build_acquire_sh(origin_url=str(archive), source_type="zip"),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (upstream / "main.py").read_text() == "print('zip')\n"


def test_origin_with_single_quote_stays_quoted():
    nasty = "https://example.com/'; rm -rf /; echo '"
    script = build_acquire_sh(origin_url=nasty, source_type="git").decode()
    assert _sh_n(script.encode()).returncode == 0, "injected quote broke script syntax"
    assert "'\\''" in script


def test_usage_error_on_extra_arg(tmp_path):
    result = _run(build_acquire_sh(), tmp_path, "unexpected")
    assert result.returncode == 2
    assert "usage" in result.stderr
