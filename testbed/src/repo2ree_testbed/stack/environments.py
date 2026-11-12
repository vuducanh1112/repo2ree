"""The machines a store's workbench can be installed on, each an image (testbed/environments/)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from repo2ree_testbed.stack.docker import engine_side

# What the stack gives a workbench it runs from source, and the machine's image already holds.
_SOURCE_ONLY = frozenset(
    {"REPO2REE_EXEC_PATH", "WORKBENCH_ENGINE_PATH", "WORKBENCH_SCRIPT_ENGINE", "WORKBENCH_TOOLS_BUNDLE"}
)


class EnvironmentName(StrEnum):
    BARE = "bare"
    DOCKER = "docker"
    PODMAN = "podman"
    PODMAN_HOST = "podman-host"
    SLURM = "slurm"


DNS_VARIABLE = "REPO2REE_ENVIRONMENT_DNS"


@dataclass(frozen=True)
class Environment:
    name: EnvironmentName
    # Where a workbench on this machine runs the author's scripts, and with which engine.
    backend: Literal["container", "host"]
    engine: str = ""
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


ENVIRONMENTS: dict[EnvironmentName, Environment] = {
    environment.name: environment
    for environment in (
        Environment(EnvironmentName.BARE, "host"),
        Environment(
            EnvironmentName.DOCKER,
            "container",
            engine="docker",
            privileged=True,
            scratch=("/var/lib/docker",),
            nested_daemon=True,
        ),
        Environment(EnvironmentName.PODMAN, "container", engine="podman", privileged=True),
        # The same machine, its workbench running scripts on it: an REE's own scripts call Podman.
        Environment(EnvironmentName.PODMAN_HOST, "host", privileged=True),
        Environment(EnvironmentName.SLURM, "host", privileged=True, parallel=False),
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
    merged = {**variables, **({"WORKBENCH_ENGINE": environment.engine} if environment.engine else {})}
    for variable, value in merged.items():
        if variable not in _SOURCE_ONLY:
            command += ["--env", f"{variable}={value}"]
    return [*command, environment.image, *command_on_machine]
