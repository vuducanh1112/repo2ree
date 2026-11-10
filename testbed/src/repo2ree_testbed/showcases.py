"""The example projects the suites author REEs from, and the showcases: each project and the machine it needs.

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
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName
from repo2ree_testbed.stack.store_images import DOCKER_IMAGE, PYTHON_SLIM_IMAGE


class ProjectName(StrEnum):
    APPTAINER = "apptainer"
    CONDA = "conda"
    INSTANT = "instant"
    INSTANT_DOCKER = "instant_docker"
    JAVA_MAVEN = "java_maven"
    NOTEBOOK = "notebook"
    PLOTTING = "plotting"
    PYTHON_DOCKER = "python_docker"
    PYTHON_VENV = "python_venv"
    SLURM = "slurm"
    STOCHASTIC = "stochastic"
    UNPINNED = "unpinned"


class ShowcaseName(StrEnum):
    CONDA = "conda"
    JAVA_MAVEN = "java_maven"
    NOTEBOOK = "notebook"
    PLOTTING = "plotting"
    PYTHON_DOCKER = "python_docker"
    PYTHON_VENV = "python_venv"
    SLURM = "slurm"
    STOCHASTIC = "stochastic"
    UNPINNED = "unpinned"


Workflow = Literal["authoring", "review"]
ExpectedVerdict = Literal["identical", "reproduced", "different"]
RecipeScript = Literal[
    "build_experiment_environment.sh",
    "activate_experiment_environment.sh",
    "test_activation.sh",
    "experiment.sh",
    "experiment.verify.sh",
]

PROJECTS = ROOT / "examples/projects"
API_SUITE = ROOT / "testbed/suites/showcase"
API_FEATURES = API_SUITE / "features"
GUI_SUITE = ROOT / "gui/tests/showcase"
SOURCE = "source"
RESULT = "result.txt"
# The API showcases' tier: every test of API_SUITE, each on a stack on the machine its showcase names.
API_TIER = "showcase-api"


@dataclass(frozen=True)
class Project:
    name: ProjectName
    # The bench image its REEs declare, on a machine that runs scripts in containers; None runs them on the machine.
    image: str | None
    experiment_environment_path: str
    experiment: str
    # Whether the build script is the one script inference proposes, or the recipe's.
    infer_build: bool
    verdict: ExpectedVerdict = "identical"
    # Whether its stages pull, fetch, or build over the network, and so may go quiet for long.
    network: bool = False
    outputs: tuple[str, ...] = (RESULT,)

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
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-hello",
    infer_build=True,
)
INSTANT_DOCKER = Project(
    name=ProjectName.INSTANT_DOCKER,
    image=DOCKER_IMAGE,
    experiment_environment_path=f"{SOURCE}/runtime-image.tar",
    experiment="instant-docker-hello",
    # Inference proposes `docker build` of the project as it stands; the recipe also
    # brings the bench's busybox into the build context, which a FROM scratch image needs.
    infer_build=False,
)
APPTAINER = Project(
    name=ProjectName.APPTAINER,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime.sif",
    experiment="instant-apptainer-hello",
    infer_build=False,
)
PYTHON_DOCKER = Project(
    name=ProjectName.PYTHON_DOCKER,
    image=DOCKER_IMAGE,
    experiment_environment_path=f"{SOURCE}/runtime.tar",
    experiment="python-hello",
    infer_build=False,
    network=True,
)
PYTHON_VENV = Project(
    name=ProjectName.PYTHON_VENV,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="python-pip-hello",
    infer_build=False,
    network=True,
)
JAVA_MAVEN = Project(
    name=ProjectName.JAVA_MAVEN,
    image=DOCKER_IMAGE,
    experiment_environment_path=f"{SOURCE}/runtime.tar",
    experiment="java-hello",
    infer_build=False,
    network=True,
)
SLURM = Project(
    name=ProjectName.SLURM,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-slurm-hello",
    infer_build=True,
)
STOCHASTIC = Project(
    name=ProjectName.STOCHASTIC,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-stochastic-pi",
    infer_build=True,
    verdict="reproduced",
)
CONDA = Project(
    name=ProjectName.CONDA,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-conda.tar.gz",
    experiment="conda-numpy",
    infer_build=False,
    network=True,
)
NOTEBOOK = Project(
    name=ProjectName.NOTEBOOK,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="notebook-decay-rate",
    infer_build=True,
    # The executed notebook records when each of its cells ran, so no rerun repeats its bytes.
    verdict="reproduced",
    network=True,
    outputs=(RESULT, "curve.csv", "figure.json", "figure.png", "executed.ipynb"),
)
PLOTTING = Project(
    name=ProjectName.PLOTTING,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="plotting-linear-fit",
    infer_build=True,
    network=True,
    outputs=(RESULT, "fit.csv", "figure.png"),
)
UNPINNED = Project(
    name=ProjectName.UNPINNED,
    image=None,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="unpinned-mean-kelvin",
    infer_build=False,
    verdict="different",
)
ALL_PROJECTS: tuple[Project, ...] = (
    APPTAINER,
    CONDA,
    INSTANT,
    INSTANT_DOCKER,
    JAVA_MAVEN,
    NOTEBOOK,
    PLOTTING,
    PYTHON_DOCKER,
    PYTHON_VENV,
    SLURM,
    STOCHASTIC,
    UNPINNED,
)


@dataclass(frozen=True)
class ShowcaseConfig:
    project: Project
    environment: EnvironmentName


SHOWCASES: dict[ShowcaseName, ShowcaseConfig] = {
    ShowcaseName.CONDA: ShowcaseConfig(CONDA, EnvironmentName.BARE),
    ShowcaseName.JAVA_MAVEN: ShowcaseConfig(JAVA_MAVEN, EnvironmentName.DOCKER),
    ShowcaseName.NOTEBOOK: ShowcaseConfig(NOTEBOOK, EnvironmentName.BARE),
    ShowcaseName.PLOTTING: ShowcaseConfig(PLOTTING, EnvironmentName.BARE),
    ShowcaseName.PYTHON_DOCKER: ShowcaseConfig(PYTHON_DOCKER, EnvironmentName.DOCKER),
    ShowcaseName.PYTHON_VENV: ShowcaseConfig(PYTHON_VENV, EnvironmentName.BARE),
    ShowcaseName.SLURM: ShowcaseConfig(SLURM, EnvironmentName.SLURM),
    ShowcaseName.STOCHASTIC: ShowcaseConfig(STOCHASTIC, EnvironmentName.BARE),
    ShowcaseName.UNPINNED: ShowcaseConfig(UNPINNED, EnvironmentName.BARE),
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


def api_suites() -> tuple[Path, ...]:
    return (*(api_suite(name) for name in SHOWCASES), API_FEATURES)


def machine_of(node: str) -> EnvironmentName:
    """The machine an API test runs on, by the showcase, or the features, whose folder holds it."""
    parts = Path(node.split("::", 1)[0]).parts
    suite = API_SUITE.relative_to(ROOT).parts
    if parts[: len(suite)] != suite or len(parts) <= len(suite) + 1:
        raise ValueError(f"{node} is no test of an API showcase")
    folder = parts[len(suite)]
    if folder == API_FEATURES.name:
        return FEATURES_ENVIRONMENT
    return SHOWCASES[ShowcaseName(folder)].environment
