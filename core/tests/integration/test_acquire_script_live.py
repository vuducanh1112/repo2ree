import os
import shutil
import subprocess
from pathlib import Path

import pytest

from repo2ree_core.persistence.layout import ACQUIRE_SCRIPT_FILENAME, UPSTREAM_DIRNAME
from repo2ree_core.reproduction.acquire_source import build_acquire_sh

_LIVE_ORIGIN = "https://github.com/vuducanh1112/repo2ree.git"
_LIVE_PINNED_COMMIT = "1fbbca3e81f09798afdb36729b358289829dda94"


def _run(script: bytes, tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
    path = tmp / ACQUIRE_SCRIPT_FILENAME
    path.write_bytes(script)
    return subprocess.run(["sh", str(path), *args], text=True, capture_output=True)


def _skip_unless_remote_reachable(url: str) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is required to reach the live remote")
    probe = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        capture_output=True,
        timeout=30,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if probe.returncode != 0:
        pytest.skip("requires network access to the public repo2ree git remote")


def test_pins_to_recorded_commit_against_a_real_remote(tmp_path):
    _skip_unless_remote_reachable(_LIVE_ORIGIN)
    upstream = tmp_path / UPSTREAM_DIRNAME
    result = _run(
        build_acquire_sh(origin_url=_LIVE_ORIGIN, source_type="git", revision=_LIVE_PINNED_COMMIT),
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    head = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert head == _LIVE_PINNED_COMMIT
