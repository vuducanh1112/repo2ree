"""The example projects the suites author REEs from.

A project is a folder of ``examples/projects``: ``source/`` is the tree that gets uploaded, unpacking to
``source/`` in the workspace, and ``recipe/`` holds the scripts that run it.
"""

from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.run_watch import INSTANT_RUN, QUIET_NETWORK_RUN, RunWatch
from repo2ree_testbed.stack.store_images import DOCKER_IMAGE, PYTHON_SLIM_IMAGE


class ProjectName(StrEnum):
    APPTAINER = "apptainer"
    INSTANT = "instant"
    INSTANT_DOCKER = "instant_docker"
    JAVA_MAVEN = "java_maven"
    PYTHON_DOCKER = "python_docker"
    PYTHON_VENV = "python_venv"
    SLURM = "slurm"
    STOCHASTIC = "stochastic"


ExpectedVerdict = Literal["identical", "reproduced"]
RecipeScript = Literal["build_script.sh", "activation.sh", "experiment.sh", "experiment.verify.sh"]

PROJECTS = ROOT / "examples/projects"
SOURCE = "source"


@dataclass(frozen=True)
class Project:
    name: ProjectName
    # The bench image its REEs declare, on a machine that runs scripts in containers; None runs them on the machine.
    image: str | None
    runtime: str
    experiment: str
    # Whether the build script is the one script inference proposes, or the recipe's.
    infer_build: bool
    verdict: ExpectedVerdict = "identical"
    # Whether its stages pull, fetch, or build over the network, and so may go quiet for long.
    network: bool = False

    @property
    def directory(self) -> Path:
        return PROJECTS / self.name

    @property
    def source(self) -> Path:
        return self.directory / SOURCE

    @property
    def upload_name(self) -> str:
        return f"{self.name.replace('_', '-')}.tar.gz"

    @property
    def watch(self) -> RunWatch:
        return QUIET_NETWORK_RUN if self.network else INSTANT_RUN

    @property
    def experiment_script(self) -> str:
        return f"ree-scripts/experiments/{self.experiment}.sh"

    @property
    def experiment_verify(self) -> str:
        return f"ree-scripts/experiments/{self.experiment}.verify.sh"

    def recipe(self, script: RecipeScript) -> str:
        return (self.directory / "recipe" / script).read_text()

    def archive(self) -> bytes:
        """The source tree packed as an upload, without interpreter caches."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(self.source, arcname=SOURCE, filter=lambda info: None if "__pycache__" in info.name else info)
        return buffer.getvalue()


INSTANT = Project(
    name=ProjectName.INSTANT,
    image=PYTHON_SLIM_IMAGE,
    runtime=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-hello",
    infer_build=True,
)
INSTANT_DOCKER = Project(
    name=ProjectName.INSTANT_DOCKER,
    image=DOCKER_IMAGE,
    runtime=f"{SOURCE}/runtime-image.tar",
    experiment="instant-docker-hello",
    # Inference proposes `docker build` of the project as it stands; the recipe also
    # brings the bench's busybox into the build context, which a FROM scratch image needs.
    infer_build=False,
)
APPTAINER = Project(
    name=ProjectName.APPTAINER,
    image=None,
    runtime=f"{SOURCE}/runtime.sif",
    experiment="instant-apptainer-hello",
    infer_build=False,
)
PYTHON_DOCKER = Project(
    name=ProjectName.PYTHON_DOCKER,
    image=DOCKER_IMAGE,
    runtime=f"{SOURCE}/runtime.tar",
    experiment="python-hello",
    infer_build=False,
    network=True,
)
PYTHON_VENV = Project(
    name=ProjectName.PYTHON_VENV,
    image=None,
    runtime=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="python-pip-hello",
    infer_build=False,
    network=True,
)
JAVA_MAVEN = Project(
    name=ProjectName.JAVA_MAVEN,
    image=DOCKER_IMAGE,
    runtime=f"{SOURCE}/runtime.tar",
    experiment="java-hello",
    infer_build=False,
    network=True,
)
SLURM = Project(
    name=ProjectName.SLURM,
    image=None,
    runtime=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-slurm-hello",
    infer_build=True,
)
STOCHASTIC = Project(
    name=ProjectName.STOCHASTIC,
    image=None,
    runtime=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-stochastic-pi",
    infer_build=True,
    verdict="reproduced",
)
ALL_PROJECTS: tuple[Project, ...] = (
    APPTAINER,
    INSTANT,
    INSTANT_DOCKER,
    JAVA_MAVEN,
    PYTHON_DOCKER,
    PYTHON_VENV,
    SLURM,
    STOCHASTIC,
)
