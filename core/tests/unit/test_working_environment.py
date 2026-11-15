"""How ``ree`` enters the working environment an REE declares, on the machine its environment describes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo2ree_core.execution import working_environment as we
from repo2ree_core.execution.launch import Launch
from repo2ree_core.execution.runners import run_workspace_script
from repo2ree_core.execution.working_environment import (
    ApptainerEntry,
    ContainerEntry,
    HostEntry,
    Machine,
    RefusedEntry,
    WorkingEnvironmentUnavailableError,
)
from repo2ree_ree.reserved_paths import RESERVED_LAUNCH_SCRIPT
from repo2ree_ree.working_environment import WorkingEnvironment

PINNED = WorkingEnvironment(oci=f"docker.io/library/python:3.12@sha256:{'b' * 64}")
UNPINNED = WorkingEnvironment(oci="docker.io/library/python:3.12")
_VARIABLES = (
    we.ENGINE_VARIABLE,
    we.SCRIPT_ENGINE_VARIABLE,
    we.ENGINE_PATH_VARIABLE,
    we.JOB_OWNER_VARIABLE,
    we.HOST_SCRIPTS_VARIABLE,
)


@pytest.fixture(autouse=True)
def _no_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_told_nothing_a_machine_runs_host_scripts_and_finds_its_engine_on_path() -> None:
    assert Machine.from_environment() == Machine()
    assert isinstance(Machine().enter(None), HostEntry)


def test_a_machine_reads_its_engine_and_where_the_engine_sees_its_files(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(we.ENGINE_VARIABLE, "podman")
    monkeypatch.setenv(we.SCRIPT_ENGINE_VARIABLE, "socket")
    monkeypatch.setenv(we.ENGINE_PATH_VARIABLE, "/store=/srv/store")
    monkeypatch.setenv(we.JOB_OWNER_VARIABLE, "/store")
    monkeypatch.setenv(we.HOST_SCRIPTS_VARIABLE, "refused")
    machine = Machine.from_environment()
    assert machine == Machine("podman", "socket", ("/store", "/srv/store"), "/store", "refused")
    entry = machine.enter(UNPINNED)
    assert isinstance(entry, ContainerEntry)
    assert (entry.engine, entry.script_engine, entry.engine_path, entry.owner) == (
        "podman",
        "socket",
        ("/store", "/srv/store"),
        "/store",
    )


def test_a_machine_refuses_an_engine_it_does_not_know(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(we.ENGINE_VARIABLE, "lxc")
    with pytest.raises(ValueError, match="names no engine"):
        Machine.from_environment()


def test_a_machine_that_runs_no_host_scripts_refuses_an_ree_that_declares_no_image() -> None:
    entry = Machine(host_scripts="refused").enter(None)
    assert isinstance(entry, RefusedEntry)
    for use in (lambda: entry.prepare(lambda *_: None), lambda: entry.observe()):
        with pytest.raises(WorkingEnvironmentUnavailableError, match="declare the OCI image"):
            use()


def test_a_machine_without_an_engine_refuses_an_ree_that_declares_an_image(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(Machine(engine="none").enter(PINNED), RefusedEntry)
    monkeypatch.setenv("PATH", "")
    assert isinstance(Machine().enter(PINNED), RefusedEntry)


def test_apptainer_runs_a_pinned_image_or_the_one_the_bundle_carries(tmp_path: Path) -> None:
    machine = Machine(engine="apptainer")
    assert isinstance(machine.enter(UNPINNED), RefusedEntry)

    entry = machine.enter(PINNED)
    assert isinstance(entry, ApptainerEntry)
    entry.prepare(lambda *_: None)
    workspace = tmp_path / "workspace"
    assert entry.command(workspace, ["sh", "run.sh"]) == [
        *("apptainer", "exec", "--bind", f"{workspace}:{workspace}", "--pwd", str(workspace)),
        *(f"docker://{PINNED.oci}", "sh", "run.sh"),
    ]
    observed = entry.observe()
    assert (observed.backend, observed.image_digest, observed.image_source) == (
        "container",
        f"sha256:{'b' * 64}",
        "engine",
    )

    archive = tmp_path / "working-environment.tar"
    archive.write_bytes(b"image")
    assert isinstance(machine.enter(UNPINNED, bundled=archive), RefusedEntry)
    bundled = machine.enter(PINNED, bundled=archive)
    bundled.prepare(lambda *_: None)
    assert f"docker-archive:{archive}" in bundled.command(workspace, ["true"])
    assert bundled.observe().image_source == "bundle"


def test_a_container_runs_the_image_by_its_id_with_only_the_workspace_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(we, "_inspect", lambda _engine, _image: (f"sha256:{'a' * 64}", f"sha256:{'b' * 64}"))
    entry = Machine(engine="docker", owner="/store").enter(PINNED)
    entry.prepare(lambda *_: None)
    command = entry.command(tmp_path, ["sh", "run.sh"])
    assert command[:5] == ["docker", "run", "--rm", "--init", "--name"]
    assert ["-v", f"{tmp_path}:{tmp_path}"] == command[command.index("-v") : command.index("-v") + 2]
    assert command[-4:] == [str(tmp_path), f"sha256:{'a' * 64}", "sh", "run.sh"]
    assert f"{we.JOB_OWNER_LABEL}=/store" in command
    observed = entry.observe()
    assert (observed.declared, observed.image_digest, observed.image_source) == (PINNED, f"sha256:{'b' * 64}", "engine")


def test_an_image_the_engine_cannot_pull_is_loaded_from_the_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded: list[str] = []
    archive = tmp_path / "working-environment.tar"
    archive.write_bytes(b"image")

    def inspect(_engine: str, image: str) -> tuple[str, str] | None:
        return (
            (f"sha256:{'c' * 64}", f"sha256:{'c' * 64}") if loaded and image == we.bundled_image_name(PINNED) else None
        )

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[1] == "load":
            loaded.append(command[-1])
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "manifest unknown")

    monkeypatch.setattr(we, "_inspect", inspect)
    monkeypatch.setattr(subprocess, "run", run)
    entry = Machine(engine="podman").enter(PINNED, bundled=archive)
    entry.prepare(lambda *_: None)
    assert loaded == [str(archive)]
    assert entry.observe().image_source == "bundle"


def test_an_image_neither_pulled_nor_bundled_stops_the_script_with_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(we, "_inspect", lambda *_: None)
    monkeypatch.setattr(
        subprocess, "run", lambda command, **_: subprocess.CompletedProcess(command, 1, "", "manifest unknown")
    )
    (tmp_path / "step.sh").write_text("true\n")
    outcome = run_workspace_script(
        tmp_path, "step.sh", log=lambda *_: None, entry=Machine(engine="docker").enter(PINNED)
    )
    assert outcome.status == "failed"


def test_the_launch_wraps_the_entry_so_a_job_enters_the_image_where_it_landed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(we, "_inspect", lambda *_: (f"sha256:{'a' * 64}", f"sha256:{'a' * 64}"))
    scripts = tmp_path / "ree-scripts"
    scripts.mkdir()
    # Stands in for srun: writes down the command it was handed instead of running it.
    (tmp_path / RESERVED_LAUNCH_SCRIPT).write_text('printf "%s\\n" "$@" > launched.txt\n')
    (scripts / "step.sh").write_text("true\n")
    run_workspace_script(
        tmp_path,
        "ree-scripts/step.sh",
        log=lambda *_: None,
        launch=Launch(script=RESERVED_LAUNCH_SCRIPT),
        entry=Machine(engine="docker").enter(PINNED),
    )
    launched = (tmp_path / "launched.txt").read_text().splitlines()
    # The recorder runs first, outside the image; then the engine enters it, and the script runs inside.
    assert launched.index("docker") > launched.index("-c")
    assert launched[-2:] == ["sh", "ree-scripts/step.sh"]


@pytest.mark.parametrize(
    ("printed", "expected"),
    [
        # Docker names the id's algorithm; Podman prints the id alone.
        (f"sha256:{'a' * 64} repo@sha256:{'b' * 64}", (f"sha256:{'a' * 64}", f"sha256:{'b' * 64}")),
        (f"{'a' * 64} repo@sha256:{'b' * 64}", (f"sha256:{'a' * 64}", f"sha256:{'b' * 64}")),
        # An image no registry holds is known by its id.
        (f"sha256:{'a' * 64} ", (f"sha256:{'a' * 64}", f"sha256:{'a' * 64}")),
        (f"{'a' * 64} ", (f"sha256:{'a' * 64}", f"sha256:{'a' * 64}")),
        ("", None),
    ],
)
def test_an_image_is_known_by_its_id_whichever_engine_prints_it(
    monkeypatch: pytest.MonkeyPatch, printed: str, expected: tuple[str, str] | None
) -> None:
    inspected = subprocess.CompletedProcess[str]([], 0, stdout=f"{printed}\n")
    monkeypatch.setattr(subprocess, "run", lambda *_, **__: inspected)

    assert we._inspect("engine", "image") == expected
