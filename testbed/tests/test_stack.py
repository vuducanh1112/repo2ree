import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from repo2ree_testbed.stack import images as image_stack
from repo2ree_testbed.stack import workbench_cleanup as cleanup
from repo2ree_testbed.stack.process import descendants, kill_tree


def test_each_further_store_has_a_workbench_and_a_directory_of_its_own() -> None:
    assert image_stack.ImageStack.workbench_name(3) == "repo2ree-workbench-3"
    store = image_stack.ImageStack.store_environment(3)
    assert (store["REPO2REE_STORE_ID"], store["REPO2REE_STORE_DIR"]) == ("lab-3", f"{image_stack.STORE_ROOT}/lab-3")


def test_global_cleanup_takes_only_job_and_bench_containers_and_unused_anonymous_volumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anonymous = "a" * 64

    def fake_lines(args: list[str]) -> list[str]:
        query = " ".join(args)
        if "name=^repo2ree-job-" in query:
            return ["job-1"]
        if "name=^repo2ree-wb-" in query:
            return ["bench-1"]
        if "dangling=true" in query:
            return [anonymous, "unrelated-volume"]
        return []

    monkeypatch.setattr(cleanup, "lines", fake_lines)

    assert cleanup.workbench_containers(None) == ["bench-1", "job-1"]
    assert cleanup.global_volumes() == [anonymous]


def test_stack_clis_reject_invalid_combinations() -> None:
    commands = (
        ["images", "up", "--compute-locations", "0"],
        ["e2e", "--script", "walkthrough.py"],
        ["e2e", "--script", "suite.py", "--tier", "t", "--jobs", "2"],
        ["e2e", "--script", "suite.py", "--tier", "t", "--select", "test_x"],
        [
            "image-suite",
            "--suite",
            "showcase",
            "--compute-locations",
            "1",
            "--images",
            "published",
        ],
        [
            "image-suite",
            "--suite",
            "showcase",
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


def _alive(pid: int) -> bool:
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


def test_a_killed_workbench_takes_the_processes_it_started_with_it(tmp_path: Path) -> None:
    started = tmp_path / "started"
    script = (
        "import subprocess, time\n"
        "child = subprocess.Popen(['sleep', '60'], start_new_session=True)\n"
        f"open({str(started)!r}, 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    workbench = subprocess.Popen([sys.executable, "-c", script], start_new_session=True)
    deadline = time.monotonic() + 10
    while not (started.exists() and started.read_text()):
        assert time.monotonic() < deadline
        time.sleep(0.05)
    executor = int(started.read_text())
    assert executor in descendants(workbench.pid)

    kill_tree(workbench)

    assert workbench.returncode == -signal.SIGKILL
    deadline = time.monotonic() + 5
    while _alive(executor):
        assert time.monotonic() < deadline, "the executor outlived its workbench"
        time.sleep(0.05)
