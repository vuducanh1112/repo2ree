"""The machines a store's workbench can be installed on, each an image (testbed/environments/)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.stack.docker import engine_side

# What the stack gives a workbench it runs from source, and the machine's image already holds.
_SOURCE_ONLY = frozenset({"REPO2REE_CLI_PATH", "WORKBENCH_TOOLS_BUNDLE"})


class EnvironmentName(StrEnum):
    BARE = "bare"
    DOCKER = "docker"
    PODMAN = "podman"
    SLURM = "slurm"


DNS_VARIABLE = "REPO2REE_ENVIRONMENT_DNS"
# Where `just _load-environment <name>` links each machine's image and records the tag it loaded as.
LOADED = ROOT / "dist" / "environments"


@dataclass(frozen=True)
class Environment:
    name: EnvironmentName
    # The container engine the machine offers its scripts, if any.
    engine: Literal["docker", "podman", ""] = ""
    # Starts services as root, which then drop to the user; what else it may do, a daemon needs.
    privileged: bool = False
    # Directories its services write to that the image's own layers cannot hold.
    scratch: tuple[str, ...] = ()
    # Whether it runs a Docker daemon of its own, which needs telling the host's DNS servers.
    nested_daemon: bool = False

    @property
    def image(self) -> str:
        """The machine's image as this checkout built and loaded it, tagged by what it holds."""
        loaded = LOADED / f"{self.name}.image"
        try:
            return loaded.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            raise RuntimeError(
                f"the {self.name} machine's image is not loaded from this checkout: just _load-environment {self.name}"
            ) from None


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
        Environment(EnvironmentName.SLURM, privileged=True),
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
    for variable, value in variables.items():
        if variable not in _SOURCE_ONLY:
            command += ["--env", f"{variable}={value}"]
    return [*command, environment.image, *command_on_machine]


# The machine a stack's first store runs on, as its test client finds it: the environment, the container, and a
# directory the client and the machine share at the same path.
MACHINE_VARIABLE = "E2E_MACHINE"
MACHINE_CONTAINER_VARIABLE = "E2E_MACHINE_CONTAINER"
MACHINE_WORKDIR_VARIABLE = "E2E_MACHINE_WORKDIR"


def machine_exec(
    environment: Environment,
    container: str,
    command_on_machine: Sequence[str],
    variables: Mapping[str, str] | None = None,
    workdir: Path | None = None,
) -> list[str]:
    """The command that runs ``command_on_machine`` on a running machine, as the user who logs in to it, in
    ``workdir`` where one is named.

    With the machine's own environment: its PATH, the workbench's tools and ``ree``, and ``variables`` beside it. A
    machine whose services start as root has its user's home and runtime directory, as its entrypoint gives the
    workbench.
    """
    uid, gid = os.getuid(), os.getgid()
    command = ["docker", "exec", "--interactive", "--user", f"{uid}:{gid}"]
    if environment.privileged:
        command += ["--env", "HOME=/home/researcher", "--env", f"XDG_RUNTIME_DIR=/run/user/{uid}"]
    for name, value in (variables or {}).items():
        command += ["--env", f"{name}={value}"]
    if workdir is not None:
        command += ["--workdir", str(workdir)]
    return [*command, container, *command_on_machine]
