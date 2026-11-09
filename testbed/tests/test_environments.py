from pathlib import Path

import pytest

from repo2ree_testbed.runs.e2e import parse
from repo2ree_testbed.runs.environment import probe
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName, machine_command


def command(name: str) -> list[str]:
    return machine_command(
        ENVIRONMENTS[EnvironmentName(name)],
        {"WORKBENCH_STORE": "lab-1=/state/store", "WORKBENCH_TOOLS_BUNDLE": "/dist/tools"},
        ("repo2ree-workbench", "--flag"),
        container="run-1",
        owner="run",
        network="lab",
        mounts=(Path("/state"),),
    )


def test_a_workbench_installed_on_a_machine_gets_only_what_the_machine_lacks() -> None:
    bare = command("bare")

    assert "WORKBENCH_STORE=lab-1=/state/store" in bare
    assert not any("WORKBENCH_TOOLS_BUNDLE" in part for part in bare)
    assert bare[-3:] == [ENVIRONMENTS[EnvironmentName.BARE].image, "repo2ree-workbench", "--flag"]


def test_a_machine_with_services_starts_as_root_and_is_told_the_user() -> None:
    assert "--user" in command("bare")
    assert "--privileged" not in command("bare")
    assert "--privileged" in command("docker")
    assert any(part.startswith("REPO2REE_ENVIRONMENT_USER=") for part in command("docker"))


def test_a_machine_names_the_engine_its_scripts_run_with() -> None:
    assert "WORKBENCH_ENGINE=podman" in command("podman")
    assert not any(part.startswith("WORKBENCH_ENGINE=") for part in command("slurm"))


def test_a_machines_scratch_volume_carries_its_owner_for_cleanup() -> None:
    mount = "type=volume,source=run-1-scratch-0,target=/var/lib/docker,volume-label=repo2ree.resource-owner=run"

    assert mount in command("docker")


def test_a_check_runs_a_container_where_the_machine_has_an_engine() -> None:
    assert "repo2ree-workbench --help" in probe(ENVIRONMENTS[EnvironmentName.BARE])
    assert "docker run --rm" not in probe(ENVIRONMENTS[EnvironmentName.BARE])
    assert "docker run --rm" in probe(ENVIRONMENTS[EnvironmentName.DOCKER])
    assert "podman run --rm" in probe(ENVIRONMENTS[EnvironmentName.PODMAN])


@pytest.mark.parametrize(
    ("name", "backend"), [("bare", "host"), ("docker", "container"), ("podman", "container"), ("slurm", "host")]
)
def test_a_machine_says_where_its_scripts_run(name: str, backend: str) -> None:
    args = ["--script", "suite.py", "--tier", f"e2e-environment-{name}", "--environment", name]

    deployment = parse(args).deployment

    assert deployment.environment == ENVIRONMENTS[EnvironmentName(name)]
    assert deployment.backend == backend
