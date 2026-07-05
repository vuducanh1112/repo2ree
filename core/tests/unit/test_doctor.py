"""The bench capability probe: hard contract vs. capability inventory."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.doctor import run_doctor


def test_writable_ree_is_ok(tmp_path: Path) -> None:
    report = run_doctor(ree_path=tmp_path, docker_wait_seconds=0)
    assert report["ok"] is True
    assert report["reeWritable"] is True
    # Capability inventory is always present, whatever it found.
    assert set(report["tools"]) == {"syft", "git", "curl", "unzip", "tar", "gzip"}
    assert "available" in report["docker"]


def test_missing_ree_fails_the_contract(tmp_path: Path) -> None:
    report = run_doctor(ree_path=tmp_path / "nope", docker_wait_seconds=0)
    assert report["ok"] is False
    assert report["reeWritable"] is False


def test_unwritable_ree_fails_the_contract(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir(mode=0o500)
    try:
        report = run_doctor(ree_path=locked, docker_wait_seconds=0)
    finally:
        locked.chmod(0o700)
    if report["reeWritable"]:  # running as root, nothing is unwritable
        pytest.skip("cannot make a directory unwritable for this uid")
    assert report["ok"] is False
