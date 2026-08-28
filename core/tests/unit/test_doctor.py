"""The bench capability probe: hard contract vs. capability inventory."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo2ree_core import doctor as doctor_mod
from repo2ree_core.doctor import run_doctor


def test_writable_ree_is_ok(tmp_path: Path) -> None:
    report = run_doctor(ree_path=tmp_path, docker_wait_seconds=0)
    assert report["ok"] is True
    assert report["ree_writable"] is True
    # Capability inventory is always present, whatever it found.
    assert set(report["tools"]) == {"syft", "git", "curl", "unzip", "tar", "gzip", "shellcheck"}
    assert "available" in report["docker"]


def test_missing_ree_fails_the_contract(tmp_path: Path) -> None:
    report = run_doctor(ree_path=tmp_path / "nope", docker_wait_seconds=0)
    assert report["ok"] is False
    assert report["ree_writable"] is False


def test_unwritable_ree_fails_the_contract(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    try:
        report = run_doctor(ree_path=locked, docker_wait_seconds=0)
    finally:
        locked.chmod(0o700)
    if report["ree_writable"]:  # running as root, nothing is unwritable
        pytest.skip("cannot make a directory unwritable for this uid")
    assert report["ok"] is False


def test_docker_probe_survives_a_hanging_daemon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `docker info` that blocks past its timeout is a still-starting daemon,
    not a crash. The probe must report docker unavailable and let the hard
    contract stand — never let the timeout escape, which the agent reads as a
    failed bench contract and fails provisioning on a merely-slow substrate."""
    monkeypatch.setattr(doctor_mod, "find_tool", lambda name: "/usr/bin/docker" if name == "docker" else None)

    def _hang(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="docker info", timeout=10)

    monkeypatch.setattr(subprocess, "run", _hang)

    report = run_doctor(ree_path=tmp_path, docker_wait_seconds=0)

    assert report["ok"] is True  # /ree is writable — the hard contract still holds
    assert report["docker"]["available"] is False
    assert "did not respond" in report["docker"]["detail"]
