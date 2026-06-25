from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import repo2ree_core.container.runtime_image as runtime_image_mod
from repo2ree_core.container.runtime_image import loaded_runtime_image


def test_loaded_runtime_image_removes_run_tag_and_loaded_ref_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls = _patch_successful_docker(monkeypatch)

    with loaded_runtime_image(tmp_path / "runtime.tar", run_id="run123", log=lambda *_: None) as image:
        assert image == "repo2ree-runtime-run123"

    assert run_calls[-1] == [
        "docker",
        "rmi",
        "-f",
        "repo2ree-runtime-run123",
        "registry.example/runtime:v1",
    ]


def test_loaded_runtime_image_preserves_loaded_ref_when_base_image_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_calls = _patch_successful_docker(monkeypatch)

    with loaded_runtime_image(
        tmp_path / "runtime.tar",
        run_id="run456",
        log=lambda *_: None,
        preserve_base_image=True,
    ) as image:
        assert image == "repo2ree-runtime-run456"

    assert run_calls[-1] == [
        "docker",
        "rmi",
        "-f",
        "repo2ree-runtime-run456",
    ]


def _patch_successful_docker(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    run_calls: list[list[str]] = []

    def fake_run(
        argv: list[str],
        *,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        run_calls.append(argv)
        if argv[1] == "load":
            return subprocess.CompletedProcess(argv, 0, stdout="Loaded image: registry.example/runtime:v1\n", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime_image_mod.shutil, "which", lambda _: "docker")
    monkeypatch.setattr(runtime_image_mod.subprocess, "run", fake_run)
    return run_calls
