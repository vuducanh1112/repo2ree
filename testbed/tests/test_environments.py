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


def test_a_machines_scratch_volume_carries_its_owner_for_cleanup() -> None:
    mount = "type=volume,source=run-1-scratch-0,target=/var/lib/docker,volume-label=repo2ree.resource-owner=run"

    assert mount in command("docker")


def test_a_check_runs_a_container_where_the_machine_has_an_engine() -> None:
    assert "repo2ree-workbench --help" in probe(ENVIRONMENTS[EnvironmentName.BARE])
    assert "docker run --rm" not in probe(ENVIRONMENTS[EnvironmentName.BARE])
    assert "docker run --rm" in probe(ENVIRONMENTS[EnvironmentName.DOCKER])
    assert "podman run --rm" in probe(ENVIRONMENTS[EnvironmentName.PODMAN])


@pytest.mark.parametrize("name", ["bare", "docker", "podman", "slurm"])
def test_a_run_installs_its_workbenches_on_the_machine_it_names(name: str) -> None:
    args = ["--script", "suite.py", "--tier", f"e2e-environment-{name}", "--environment", name]

    deployment = parse(args).deployment

    assert deployment.environment == ENVIRONMENTS[EnvironmentName(name)]
