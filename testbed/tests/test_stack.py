import subprocess
import sys

import pytest

from repo2ree_testbed.stack import images as image_stack
from repo2ree_testbed.stack import workbench_cleanup as cleanup


def test_provider_names_remain_compatible() -> None:
    assert image_stack.ImageStack.provider_name(1) == "repo2ree-provider-docker"
    assert image_stack.ImageStack.provider_name(3) == "repo2ree-provider-docker-3"


def test_global_cleanup_selects_only_owned_name_families(monkeypatch: pytest.MonkeyPatch) -> None:
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
        ["images", "up", "--compute-locations", "0"],
        ["e2e", "--script", "walkthrough.py"],
        ["e2e", "--script", "suite.py", "--tier", "t", "--jobs", "2"],
        [
            "image-suite",
            "--suite",
            "e2e-gui",
            "--compute-locations",
            "1",
            "--images",
            "published",
        ],
        [
            "image-suite",
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
    for command in commands:
        result = subprocess.run([sys.executable, "-m", "repo2ree_testbed", *command], check=False, capture_output=True)
        assert result.returncode == 2
