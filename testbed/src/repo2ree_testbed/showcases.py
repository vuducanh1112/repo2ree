from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, get_args

from repo2ree_testbed.api_models import InferenceRule
from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.run_watch import INSTANT_RUN, QUIET_NETWORK_RUN, RunWatch
from repo2ree_testbed.stack.environments import EnvironmentName


class ProjectName(StrEnum):
    APPTAINER = "apptainer"
    CONDA = "conda"
    INSTANT = "instant"
    INSTANT_DOCKER = "instant_docker"
    JAVA_MAVEN = "java_maven"
    NOTEBOOK = "notebook"
    PLOTTING = "plotting"
    PODMAN = "podman"
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
    PODMAN = "podman"
    PYTHON_DOCKER = "python_docker"
    PYTHON_VENV = "python_venv"
    SLURM = "slurm"
    STOCHASTIC = "stochastic"
    UNPINNED = "unpinned"


Workflow = Literal["authoring", "review"]
ExpectedVerdict = Literal["identical", "reproduced", "different"]
RecipeScript = Literal[
    "check_working_environment.sh",
    "build_experiment_environment.sh",
    "activate_experiment_environment.sh",
    "launch.sh",
    "experiment.sh",
    "experiment.verify.sh",
]

PROJECTS = ROOT / "examples/projects"
API_SUITE = ROOT / "testbed/suites/showcase"
API_FEATURES = API_SUITE / "features"
GUI_SUITE = ROOT / "gui/tests/showcase"
GUI_INSTANT = ROOT / "gui/tests/e2e-instant"
SOURCE = "source"
RESULT = "result.txt"
CHECK: RecipeScript = "check_working_environment.sh"
BUILD: RecipeScript = "build_experiment_environment.sh"
ACTIVATE: RecipeScript = "activate_experiment_environment.sh"
LAUNCH: RecipeScript = "launch.sh"
REQUIRED_SCRIPTS: tuple[RecipeScript, ...] = tuple(script for script in get_args(RecipeScript) if script != LAUNCH)
SLURM_LAUNCH = ((LAUNCH, InferenceRule.SLURM_LAUNCH),)
PIP_BUILD = ((BUILD, InferenceRule.PIP_REQUIREMENTS),)
VENV = (*PIP_BUILD, (ACTIVATE, InferenceRule.VENV_ACTIVATE))
DOCKER = ((BUILD, InferenceRule.DOCKERFILE), (ACTIVATE, InferenceRule.DOCKER_ACTIVATE))
PODMAN_SCRIPTS = ((BUILD, InferenceRule.PODMAN_BUILD), (ACTIVATE, InferenceRule.PODMAN_ACTIVATE))
API_TIER = "showcase-api"
CLI_TIER = "showcase-cli"


@dataclass(frozen=True)
class Project:
    name: ProjectName
    experiment_environment_path: str
    experiment: str
    verdict: ExpectedVerdict = "identical"
    network: bool = False
    outputs: tuple[str, ...] = (RESULT,)
    inferred: tuple[tuple[RecipeScript, InferenceRule], ...] = ()

    def rule(self, script: RecipeScript) -> InferenceRule | None:
        return dict(self.inferred).get(script)

    @property
    def launches(self) -> bool:
        return self.rule(LAUNCH) is not None or (self.directory / "recipe" / LAUNCH).is_file()

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
    def check_script(self) -> str:
        return f"ree-scripts/{CHECK}"

    @property
    def experiment_script(self) -> str:
        return f"ree-scripts/experiments/{self.experiment}.sh"

    @property
    def experiment_verify(self) -> str:
        return f"ree-scripts/experiments/{self.experiment}.verify.sh"

    def recipe(self, script: RecipeScript) -> str:
        return (self.directory / "recipe" / script).read_text()

    def archive(self) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            archive.add(self.source, arcname=SOURCE, filter=lambda info: None if "__pycache__" in info.name else info)
        return buffer.getvalue()


INSTANT = Project(
    name=ProjectName.INSTANT,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-hello",
    inferred=PIP_BUILD,
)
INSTANT_DOCKER = Project(
    name=ProjectName.INSTANT_DOCKER,
    experiment_environment_path=f"{SOURCE}/runtime-image.tar",
    experiment="instant-docker-hello",
)
APPTAINER = Project(
    name=ProjectName.APPTAINER,
    experiment_environment_path=f"{SOURCE}/runtime.sif",
    experiment="instant-apptainer-hello",
    inferred=SLURM_LAUNCH,
)
PYTHON_DOCKER = Project(
    name=ProjectName.PYTHON_DOCKER,
    experiment_environment_path=f"{SOURCE}/runtime.tar",
    experiment="python-hello",
    network=True,
    inferred=DOCKER,
)
PYTHON_VENV = Project(
    name=ProjectName.PYTHON_VENV,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="python-pip-hello",
    network=True,
    inferred=VENV,
)
JAVA_MAVEN = Project(
    name=ProjectName.JAVA_MAVEN,
    experiment_environment_path=f"{SOURCE}/runtime.tar",
    experiment="java-hello",
    network=True,
    inferred=DOCKER,
)
PODMAN = Project(
    name=ProjectName.PODMAN,
    experiment_environment_path=f"{SOURCE}/runtime.tar",
    experiment="podman-hello",
    network=True,
    inferred=PODMAN_SCRIPTS,
)
SLURM = Project(
    name=ProjectName.SLURM,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-slurm-hello",
    inferred=(*VENV, *SLURM_LAUNCH),
)
STOCHASTIC = Project(
    name=ProjectName.STOCHASTIC,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="instant-stochastic-pi",
    verdict="reproduced",
    inferred=VENV,
)
CONDA = Project(
    name=ProjectName.CONDA,
    experiment_environment_path=f"{SOURCE}/runtime-conda.tar.gz",
    experiment="conda-numpy",
    network=True,
)
NOTEBOOK = Project(
    name=ProjectName.NOTEBOOK,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="notebook-decay-rate",
    verdict="reproduced",
    network=True,
    outputs=(RESULT, "curve.csv", "figure.json", "figure.png", "executed.ipynb"),
    inferred=VENV,
)
PLOTTING = Project(
    name=ProjectName.PLOTTING,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="plotting-linear-fit",
    network=True,
    outputs=(RESULT, "fit.csv", "figure.png"),
    inferred=VENV,
)
UNPINNED = Project(
    name=ProjectName.UNPINNED,
    experiment_environment_path=f"{SOURCE}/runtime-venv.tar.gz",
    experiment="unpinned-mean-kelvin",
    verdict="different",
    inferred=((ACTIVATE, InferenceRule.VENV_ACTIVATE),),
)
ALL_PROJECTS: tuple[Project, ...] = (
    APPTAINER,
    CONDA,
    INSTANT,
    INSTANT_DOCKER,
    JAVA_MAVEN,
    NOTEBOOK,
    PLOTTING,
    PODMAN,
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
    ShowcaseName.PODMAN: ShowcaseConfig(PODMAN, EnvironmentName.PODMAN),
    ShowcaseName.PYTHON_DOCKER: ShowcaseConfig(PYTHON_DOCKER, EnvironmentName.DOCKER),
    ShowcaseName.PYTHON_VENV: ShowcaseConfig(PYTHON_VENV, EnvironmentName.BARE),
    ShowcaseName.SLURM: ShowcaseConfig(SLURM, EnvironmentName.SLURM),
    ShowcaseName.STOCHASTIC: ShowcaseConfig(STOCHASTIC, EnvironmentName.BARE),
    ShowcaseName.UNPINNED: ShowcaseConfig(UNPINNED, EnvironmentName.BARE),
}
FEATURES_ENVIRONMENT = EnvironmentName.BARE

GUI_SHOWCASES: dict[ShowcaseName, dict[Workflow, str]] = {
    ShowcaseName.JAVA_MAVEN: {"authoring": "java-maven.spec.ts"},
    ShowcaseName.PYTHON_DOCKER: {"authoring": "python-docker.spec.ts", "review": "review.spec.ts"},
    ShowcaseName.PYTHON_VENV: {"authoring": "python-venv.spec.ts"},
}


def gui_machines() -> dict[Path, EnvironmentName]:
    placed = {
        GUI_SUITE / spec: SHOWCASES[name].environment
        for name, specs in GUI_SHOWCASES.items()
        for spec in specs.values()
    }
    return placed | {GUI_INSTANT / "docker-authoring.spec.ts": EnvironmentName.DOCKER}


class FeatureName(StrEnum):
    ORIGINS = "origins"
    ROUTING = "routing"
    WORKING_ENVIRONMENT = "working_environment"


@dataclass(frozen=True)
class FeatureTests:
    api: Path | None
    gui: str | None


FEATURES: dict[FeatureName, FeatureTests] = {
    FeatureName.ORIGINS: FeatureTests(API_FEATURES / "test_origins.py", "origins.spec.ts"),
    FeatureName.ROUTING: FeatureTests(None, "routing.spec.ts"),
    FeatureName.WORKING_ENVIRONMENT: FeatureTests(API_FEATURES / "test_working_environment.py", None),
}


def _refusals() -> list[str]:
    refusals = [f"{name} has no config" for name in ShowcaseName if name not in SHOWCASES]
    for name, config in SHOWCASES.items():
        if config.project.name.value != name.value:
            refusals.append(f"{name} runs the project {config.project.name}")
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
    parts = Path(node.split("::", 1)[0]).parts
    suite = API_SUITE.relative_to(ROOT).parts
    if parts[: len(suite)] != suite or len(parts) <= len(suite) + 1:
        raise ValueError(f"{node} is no test of an API showcase")
    folder = parts[len(suite)]
    if folder == API_FEATURES.name:
        return FEATURES_ENVIRONMENT
    return SHOWCASES[ShowcaseName(folder)].environment
