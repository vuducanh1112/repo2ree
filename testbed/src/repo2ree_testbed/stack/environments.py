"""The machines a store's workbench can be installed on, each an image (testbed/environments/)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from repo2ree_testbed.stack.docker import engine_side
from repo2ree_testbed.stack.process import capture

# What the stack gives a workbench it runs from source, and the machine's image already holds.
_SOURCE_ONLY = frozenset({"REPO2REE_CLI_PATH", "WORKBENCH_TOOLS_BUNDLE"})


class EnvironmentName(StrEnum):
    BARE = "bare"
    DOCKER = "docker"
    PODMAN = "podman"
    SLURM = "slurm"


DNS_VARIABLE = "REPO2REE_ENVIRONMENT_DNS"
# The image a workbench runs in, as the machine reports it to the steps' receipts.
REPORTED_IMAGE_VARIABLE = "REPO2REE_IMAGE"


@dataclass(frozen=True)
class Environment:
    name: EnvironmentName
    # The container engine the machine offers its scripts, if any.
    engine: Literal["docker", "podman", ""] = ""
    # Starts services as root, which then drop to the user; what else it may do, a daemon needs.
    privileged: bool = False
    # Directories its services write to that the image's own layers cannot hold.
    scratch: tuple[str, ...] = ()
    # Whether tests may run on machines of this kind side by side.
    parallel: bool = True
    # Whether it runs a Docker daemon of its own, which needs telling the host's DNS servers.
    nested_daemon: bool = False

    @property
    def image(self) -> str:
        return f"repo2ree-environment-{self.name}:local"

    def reported_image(self) -> str:
        """The machine's image by its ref and local image id: it is loaded, never pulled, so it has no repo digest."""
        return f"{self.image}@{capture(['docker', 'image', 'inspect', '--format', '{{.Id}}', self.image], check=True)}"


ENVIRONMENTS: dict[EnvironmentName, Environment] = {
    environment.name: environment
    for environment in (
        Environment(EnvironmentName.BARE),
        Environment(
            EnvironmentName.DOCKER,
            engine="docker",
            privileged=True,
            scratch=("/var/lib/docker",),
            nested_daemon=True,
        ),
        Environment(EnvironmentName.PODMAN, engine="podman", privileged=True),
        Environment(EnvironmentName.SLURM, privileged=True, parallel=False),
    )
}


def machine_command(
    environment: Environment,
    variables: Mapping[str, str],
    command_on_machine: Sequence[str],
    *,
    container: str,
    owner: str,
    network: str,
    mounts: Sequence[Path],
    reported_image: str,
) -> list[str]:
    """The command that runs ``command_on_machine`` on ``environment``, in the foreground.

    It runs as this user, so what it leaves in the store is this process's to read and remove.
    Its scratch volumes carry the owner's label: a killed run leaves them for its cleanup to find.
    """
    user = f"{os.getuid()}:{os.getgid()}"
    command = ["docker", "run", "--rm", "--init", "--name", container, "--hostname", environment.name]
    command += ["--label", f"repo2ree.resource-owner={owner}"]
    command += ["--network", network] if network else ["--add-host", "host.docker.internal:host-gateway"]
    command += (
        ["--privileged", "--env", f"REPO2REE_ENVIRONMENT_USER={user}"] if environment.privileged else ["--user", user]
    )
    for index, target in enumerate(environment.scratch):
        volume = f"source={container}-scratch-{index},target={target},volume-label=repo2ree.resource-owner={owner}"
        command += ["--mount", f"type=volume,{volume}"]
    for path in mounts:
        command += ["--volume", f"{engine_side(path)}:{path}"]
    for variable, value in variables.items():
        if variable not in _SOURCE_ONLY:
            command += ["--env", f"{variable}={value}"]
    command += ["--env", f"{REPORTED_IMAGE_VARIABLE}={reported_image}"]
    return [*command, environment.image, *command_on_machine]


# The machine a stack's first store runs on, as its test client finds it: the environment, the container, and a
# directory the client and the machine share at the same path.
MACHINE_VARIABLE = "E2E_MACHINE"
MACHINE_CONTAINER_VARIABLE = "E2E_MACHINE_CONTAINER"
MACHINE_WORKDIR_VARIABLE = "E2E_MACHINE_WORKDIR"


def machine_exec(environment: Environment, container: str, command_on_machine: Sequence[str]) -> list[str]:
    """The command that runs ``command_on_machine`` on a running machine, as the user who logs in to it.

    With the machine's own environment: its PATH, the workbench's tools and ``ree``. A machine whose services start
    as root has its user's home and runtime directory, as its entrypoint gives the workbench.
    """
    uid, gid = os.getuid(), os.getgid()
    command = ["docker", "exec", "--interactive", "--user", f"{uid}:{gid}"]
    if environment.privileged:
        command += ["--env", "HOME=/home/researcher", "--env", f"XDG_RUNTIME_DIR=/run/user/{uid}"]
    return [*command, container, *command_on_machine]
