from types import ModuleType
from typing import Any, cast

import pytest
from conftest import ROOT, load_script


@pytest.fixture(scope="module")
def image_stack() -> ModuleType:
    return cast(ModuleType, load_script("scripts/test-stack/image_stack.py", "tested_image_stack"))


@pytest.fixture(scope="module")
def cleanup() -> ModuleType:
    return cast(ModuleType, load_script("scripts/test-stack/workbench_cleanup.py", "tested_workbench_cleanup"))


def test_provider_names_remain_compatible(image_stack: Any) -> None:
    assert image_stack.ImageStack.provider_name(1) == "repo2ree-provider-docker"
    assert image_stack.ImageStack.provider_name(3) == "repo2ree-provider-docker-3"


def test_global_cleanup_selects_only_owned_name_families(cleanup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    anonymous = "a" * 64

    def fake_lines(*args: str) -> list[str]:
        query = " ".join(args)
        if "repo2ree-ree-" in query:
            return ["repo2ree-ree-one"]
        if "repo2ree-dind-" in query:
            return ["repo2ree-dind-one"]
        if "dangling=true" in query:
            return [anonymous, "unrelated-volume"]
        return []

    monkeypatch.setattr(cleanup, "lines", fake_lines)

    assert cleanup.global_volumes(False) == [anonymous, "repo2ree-dind-one", "repo2ree-ree-one"]


def test_stack_clis_reject_invalid_combinations() -> None:
    commands = (
        ["scripts/test-stack/image_stack.py", "up", "--compute-locations", "0"],
        ["scripts/test-stack/e2e_stack.py", "--script", "walkthrough.py"],
        [
            "scripts/test-stack/run_image_suite.py",
            "--suite",
            "e2e-gui",
            "--compute-locations",
            "1",
            "--images",
            "published",
        ],
        [
            "scripts/test-stack/run_image_suite.py",
            "--suite",
            "e2e-gui",
            "--compute-locations",
            "1",
            "--images",
            "published",
            "--repository",
            "registry/team",
            "--tag",
            "revision-1",
            "--existing",
        ],
    )
    import subprocess
    import sys

    for command in commands:
        result = subprocess.run(
            [sys.executable, str(ROOT / command[0]), *command[1:]], check=False, capture_output=True
        )
        assert result.returncode == 2
