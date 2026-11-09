"""The example projects the suites author REEs from, and the showcases: each project and the machine it needs.

A project is a folder of ``examples/projects``: ``source/`` is the tree that gets uploaded, unpacking to
``source/`` in the workspace, and ``recipe/`` holds the scripts that run it.
"""

from __future__ import annotations

import io
import os
import tarfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.run_watch import INSTANT_RUN, QUIET_NETWORK_RUN, RunWatch
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName
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


class ShowcaseName(StrEnum):
    JAVA_MAVEN = "java_maven"
    PYTHON_DOCKER = "python_docker"
    PYTHON_VENV = "python_venv"
    SLURM = "slurm"
    STOCHASTIC = "stochastic"


Workflow = Literal["authoring", "review"]
ExpectedVerdict = Literal["identical", "reproduced"]
RecipeScript = Literal["build_script.sh", "activation.sh", "experiment.sh", "experiment.verify.sh"]

PROJECTS = ROOT / "examples/projects"
API_SUITE = ROOT / "testbed/suites/showcase"
API_FEATURES = API_SUITE / "features"
GUI_SUITE = ROOT / "gui/tests/showcase"
SOURCE = "source"
ENVIRONMENT_VARIABLE = "SHOWCASE_ENVIRONMENT"


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


@dataclass(frozen=True)
class ShowcaseConfig:
    project: Project
    environment: EnvironmentName


SHOWCASES: dict[ShowcaseName, ShowcaseConfig] = {
    ShowcaseName.JAVA_MAVEN: ShowcaseConfig(JAVA_MAVEN, EnvironmentName.DOCKER),
    ShowcaseName.PYTHON_DOCKER: ShowcaseConfig(PYTHON_DOCKER, EnvironmentName.DOCKER),
    ShowcaseName.PYTHON_VENV: ShowcaseConfig(PYTHON_VENV, EnvironmentName.BARE),
    ShowcaseName.SLURM: ShowcaseConfig(SLURM, EnvironmentName.SLURM),
    ShowcaseName.STOCHASTIC: ShowcaseConfig(STOCHASTIC, EnvironmentName.BARE),
}
# The API tests of one feature rather than one project, and the machine they run on.
FEATURES_ENVIRONMENT = EnvironmentName.BARE

# The browser showcases each showcase has so far, by workflow: spec files of GUI_SUITE.
GUI_SHOWCASES: dict[ShowcaseName, dict[Workflow, str]] = {
    ShowcaseName.JAVA_MAVEN: {"authoring": "java-maven.spec.ts"},
    ShowcaseName.PYTHON_DOCKER: {"authoring": "python-docker.spec.ts", "review": "review.spec.ts"},
    ShowcaseName.PYTHON_VENV: {"authoring": "python-venv.spec.ts"},
}


class FeatureName(StrEnum):
    ORIGINS = "origins"
    ROUTING = "routing"


@dataclass(frozen=True)
class FeatureTests:
    """The tests of one feature rather than one project: an API test file, a browser spec file, or both."""

    api: Path | None
    gui: str | None


FEATURES: dict[FeatureName, FeatureTests] = {
    FeatureName.ORIGINS: FeatureTests(API_FEATURES / "test_origins.py", "origins.spec.ts"),
    FeatureName.ROUTING: FeatureTests(None, "routing.spec.ts"),
}


def _refusals() -> list[str]:
    """What is wrong with the showcases as declared."""
    refusals = [f"{name} has no config" for name in ShowcaseName if name not in SHOWCASES]
    for name, config in SHOWCASES.items():
        if config.project.name.value != name.value:
            refusals.append(f"{name} runs the project {config.project.name}")
        containers = ENVIRONMENTS[config.environment].backend == "container"
        if containers and config.project.image is None:
            refusals.append(f"{name} runs in containers on {config.environment} and declares no bench image")
        if not containers and config.project.image is not None:
            refusals.append(f"{name} runs directly on {config.environment} and declares a bench image")
    return refusals


if _refused := _refusals():
    raise ValueError("; ".join(_refused))


def api_suite(name: ShowcaseName) -> Path:
    return API_SUITE / name


def api_test(name: ShowcaseName, workflow: Workflow) -> Path:
    return api_suite(name) / f"test_{name}_{workflow}.py"


def environments_in_use() -> tuple[EnvironmentName, ...]:
    used = {config.environment for config in SHOWCASES.values()} | {FEATURES_ENVIRONMENT}
    return tuple(environment for environment in EnvironmentName if environment in used)


def api_suites(environment: EnvironmentName) -> tuple[Path, ...]:
    """The API suites that run on ``environment``."""
    suites = tuple(api_suite(name) for name, config in SHOWCASES.items() if config.environment == environment)
    return (*suites, API_FEATURES) if environment == FEATURES_ENVIRONMENT else suites


def api_tier(environment: EnvironmentName) -> str:
    return f"showcase-api-{environment}"


def requested_environment() -> EnvironmentName:
    """The machine this process was asked to run the API showcases on; an unknown one is refused."""
    return EnvironmentName(os.environ.get(ENVIRONMENT_VARIABLE, ""))
