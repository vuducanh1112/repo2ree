import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from repo2ree_core.persistence.layout import ACQUIRE_SCRIPT_FILENAME, SNAPSHOT_FILENAME, UPSTREAM_DIRNAME
from repo2ree_core.reproduction.acquire_source import build_acquire_sh


def _sh_n(script: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["sh", "-n", "/dev/stdin"], input=script, capture_output=True)


def _run(script: bytes, tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    path = tmp / ACQUIRE_SCRIPT_FILENAME
    path.write_bytes(script)
    return subprocess.run(["sh", str(path), *args], text=True, capture_output=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
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
    def built() -> bytes:
        return build_acquire_sh(origin_url="https://example.com/repo.git", source_type="git", swhid="swh:1:dir:x")

    assert built() == built()


def test_bakes_origin_swhid_and_only_the_relevant_fetch_command():
    script = build_acquire_sh(origin_url="https://e/r.git", source_type="git", swhid="swh:1:dir:z").decode()
    assert "ORIGIN_URL='https://e/r.git'" in script
    assert "SWHID='swh:1:dir:z'" in script
    assert "@@" not in script
    assert 'case "$SOURCE_TYPE"' not in script
    assert "git clone -q --no-tags --depth 1" in script
    assert "unzip -q" not in script


def test_a_full_history_clones_the_ancestry():
    script = build_acquire_sh(origin_url="https://e/r.git", source_type="git", history="full").decode()
    assert 'git clone -q "$ORIGIN_URL"' in script
    assert "--depth" not in script


def test_bakes_git_revision_and_pins_the_fetch():
    script = build_acquire_sh(origin_url="https://e/r.git", source_type="git", revision="deadbeef").decode()
    assert "rev='deadbeef'" in script
    assert "fetch -q --no-tags --depth 1 origin" in script
    assert "git clone" not in script


def test_a_pinned_full_history_fetches_the_revision_with_its_ancestry_and_tags():
    script = build_acquire_sh(
        origin_url="https://e/r.git", source_type="git", revision="deadbeef", history="full"
    ).decode()
    assert 'fetch -q --no-tags origin "$rev"' in script
    assert "'+refs/tags/*:refs/tags/*'" in script
    assert "--depth" not in script


def test_fetches_a_pinned_revision_with_its_history(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to exercise the generated git fetch command")
    origin = tmp_path / "origin"
    origin.mkdir()
    git = ["git", "-C", str(origin), "-c", "user.name=t", "-c", "user.email=t@e"]
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    for content in ("first", "second", "third"):
        (origin / "v.txt").write_text(f"{content}\n")
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-q", "-m", content], check=True)
        if content == "first":
            subprocess.run([*git, "tag", "-a", "v1", "-m", "v1"], check=True)
    pinned = subprocess.run([*git, "rev-parse", "HEAD~1"], check=True, capture_output=True, text=True).stdout.strip()

    result = _run(
        build_acquire_sh(origin_url=str(origin), source_type="git", revision=pinned, history="full"), tmp_path
    )

    assert result.returncode == 0, result.stderr
    upstream = tmp_path / UPSTREAM_DIRNAME
    inspect = ["git", "-C", str(upstream)]
    assert (upstream / "v.txt").read_text() == "second\n"
    assert subprocess.run([*inspect, "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout == "2\n"
    assert "v1" in subprocess.run([*inspect, "tag"], capture_output=True, text=True).stdout


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
    (origin / "v.txt").write_text("second\n")
    subprocess.run([*git, "commit", "-qa", "-m", "second"], check=True)

    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(build_acquire_sh(origin_url=str(origin), source_type="git", revision=pinned), tmp_path)
    assert result.returncode == 0, result.stderr
    assert (upstream / "v.txt").read_text() == "first\n"


def test_extracts_snapshot_when_present(tmp_path):
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
    result = _run(build_acquire_sh(), tmp_path)
    assert result.returncode == 0, result.stderr
    assert "already populated" in result.stdout
    assert (upstream / "keep.txt").exists()


def test_overlay_only_when_no_snapshot_or_origin(tmp_path):
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
