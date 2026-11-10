"""A script run in a fresh container from the REE's image: the workspace only, cancelable, and recorded."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import pytest

from repo2ree_core.execution.runners import ContainerScriptRunner
from repo2ree_protocol.frames import LogSink
from repo2ree_ree.workbench_environment import WorkbenchEnvironment

IMAGE = "alpine:3"
# Under the checkout, which a dev container shares with the engine's host (a pytest tmp_path is not).
SCRATCH = Path(__file__).resolve().parents[3] / "test-artifacts" / "core-container-runner"


@pytest.fixture
def tmp_path() -> Iterator[Path]:  # Shadows pytest's: the engine must see it.
    path = SCRATCH / uuid.uuid4().hex[:8]
    path.mkdir(parents=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _engine_path(engine: str) -> tuple[str, str] | None:
    """Where the engine sees this checkout, when this process runs in a container beside it."""
    container = os.environ.get("HOSTNAME", "")
    if not container or not Path("/.dockerenv").is_file():
        return None
    mounts = subprocess.run(
        [engine, "inspect", container, "--format", "{{range .Mounts}}{{.Destination}}={{.Source}};{{end}}"],
        capture_output=True,
        text=True,
    ).stdout
    for mount in filter(None, mounts.split(";")):
        local, _, source = mount.partition("=")
        if SCRATCH.is_relative_to(local):
            return local, source
    return None


@pytest.fixture
def engine() -> str:
    docker = shutil.which("docker")
    if docker is None or subprocess.run([docker, "image", "inspect", IMAGE], capture_output=True).returncode:
        pytest.skip(f"needs docker with {IMAGE}")
    return docker


def _logged() -> tuple[list[str], LogSink]:
    lines: list[str] = []

    def log(stream: str, level: str, message: str) -> None:
        lines.append(message)

    return lines, log


def test_a_script_sees_its_workspace_at_the_same_path_and_nothing_of_the_ree_around_it(
    engine: str, tmp_path: Path
) -> None:
    ree = tmp_path / "ree"
    workspace = ree / "workspace"
    workspace.mkdir(parents=True)
    (ree / ".git").mkdir()
    (workspace / "script.sh").write_text('pwd; test ! -e ../.git && echo "no history here"; echo built > out.txt\n')
    lines, log = _logged()
    runner = ContainerScriptRunner(engine=engine, image=IMAGE, engine_path=_engine_path(engine))

    result = runner.run(workspace, ["sh", "script.sh"], log=log, is_canceled=lambda: False)

    assert result.returncode == 0, lines
    assert str(workspace) in result.stdout
    assert "no history here" in result.stdout
    assert (workspace / "out.txt").read_text() == "built\n"
    observed = runner.observe(WorkbenchEnvironment(kind="image", image=IMAGE))
    assert observed.backend == "container"
    assert observed.image_digest is not None
    assert observed.image_digest.startswith("sha256:")


def test_a_canceled_script_leaves_no_container_behind(engine: str, tmp_path: Path) -> None:
    (tmp_path / "script.sh").write_text("sleep 60\n")
    _, log = _logged()
    canceled = threading.Event()
    threading.Timer(1.5, canceled.set).start()
    started = time.monotonic()

    result = ContainerScriptRunner(engine=engine, image=IMAGE, engine_path=_engine_path(engine)).run(
        tmp_path,
        ["sh", "script.sh"],
        log=log,
        is_canceled=canceled.is_set,
    )

    assert result.canceled
    assert time.monotonic() - started < 40
    left = subprocess.run([engine, "ps", "-aq", "--filter", "name=repo2ree-job-"], capture_output=True, text=True)
    assert left.stdout.strip() == ""


def test_a_script_reaches_the_host_engine_only_when_the_workbench_allows_it(engine: str, tmp_path: Path) -> None:
    (tmp_path / "script.sh").write_text("test -S /var/run/docker.sock && echo engine || echo none\n")
    _, log = _logged()

    def ran(script_engine: Literal["none", "socket"]) -> str:
        runner = ContainerScriptRunner(
            engine=engine, image=IMAGE, script_engine=script_engine, engine_path=_engine_path(engine)
        )
        return runner.run(tmp_path, ["sh", "script.sh"], log=log, is_canceled=lambda: False).stdout.strip()

    assert ran("none") == "none"
    assert ran("socket") == "engine"


def test_a_script_that_reaches_the_engine_starts_where_the_engine_sees_its_workspace(
    engine: str, tmp_path: Path
) -> None:
    (tmp_path / "script.sh").write_text(f'pwd; test -f "{tmp_path}/script.sh" && echo "local path too"\n')
    _, log = _logged()
    mapped = _engine_path(engine)
    runner = ContainerScriptRunner(engine=engine, image=IMAGE, script_engine="socket", engine_path=mapped)

    result = runner.run(tmp_path, ["sh", "script.sh"], log=log, is_canceled=lambda: False)

    assert result.stdout.splitlines() == [runner._engine_side(tmp_path), "local path too"]
