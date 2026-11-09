"""Every project is laid out alike, and every showcase has its machine and a test of each workflow."""

from typing import get_args

import pytest

from repo2ree_testbed.runs.api_showcase import e2e_arguments
from repo2ree_testbed.showcases import (
    ALL_PROJECTS,
    API_FEATURES,
    API_SUITE,
    ENVIRONMENT_VARIABLE,
    FEATURES_ENVIRONMENT,
    PROJECTS,
    SHOWCASES,
    Project,
    ProjectName,
    RecipeScript,
    ShowcaseName,
    Workflow,
    api_suite,
    api_suites,
    api_test,
    environments_in_use,
    requested_environment,
)
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName


@pytest.mark.parametrize("name", list(ShowcaseName))
@pytest.mark.parametrize("workflow", get_args(Workflow))
def test_a_showcase_has_an_api_test_of_each_workflow(name: ShowcaseName, workflow: Workflow) -> None:
    assert api_test(name, workflow).is_file()


@pytest.mark.parametrize("project", ALL_PROJECTS, ids=lambda project: project.name)
def test_a_project_is_a_source_tree_beside_its_recipe(project: Project) -> None:
    assert any(project.source.iterdir())
    for script in get_args(RecipeScript):
        if script != "build_script.sh" or not project.infer_build:
            assert project.recipe(script)


def test_every_project_folder_is_defined() -> None:
    assert {path.name for path in PROJECTS.iterdir() if path.is_dir()} == set(ProjectName)
    assert {project.name for project in ALL_PROJECTS} == set(ProjectName)


def test_every_api_suite_directory_is_a_showcase() -> None:
    ignored = {"__pycache__", API_FEATURES.name}
    assert {path.name for path in API_SUITE.iterdir() if path.is_dir() and path.name not in ignored} == set(
        ShowcaseName
    )


def test_the_map_of_showcases_is_complete() -> None:
    assert set(SHOWCASES) == set(ShowcaseName)


def test_every_machine_named_is_a_machine_there_is() -> None:
    assert set(ENVIRONMENTS) == set(EnvironmentName)


@pytest.mark.parametrize("name", list(ShowcaseName))
def test_a_showcase_runs_on_its_machine_alone(name: ShowcaseName) -> None:
    for environment in EnvironmentName:
        assert (api_suite(name) in api_suites(environment)) == (environment == SHOWCASES[name].environment)


def test_the_slurm_showcase_needs_the_slurm_machine_and_the_rest_do_not() -> None:
    assert SHOWCASES[ShowcaseName.SLURM].environment == EnvironmentName.SLURM
    assert API_FEATURES in api_suites(FEATURES_ENVIRONMENT)
    assert set(environments_in_use()) == {EnvironmentName.BARE, EnvironmentName.DOCKER, EnvironmentName.SLURM}


def test_a_tiers_run_is_what_its_machine_needs() -> None:
    assert e2e_arguments(EnvironmentName.SLURM, jobs=4, select=("a", "b"))[2:] == [
        *("--tier", "showcase-api-slurm"),
        *("--environment", "slurm"),
        *("--per-test", "--exit-on", "tests"),
        *("--jobs", "1"),
        *("--select", "a b"),
    ]
    docker = e2e_arguments(EnvironmentName.DOCKER, jobs=4)
    assert docker[docker.index("--jobs") + 1] == "4"
    assert "--select" not in docker


def test_a_machine_that_does_not_exist_is_refused_in_a_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, "slurm")
    assert requested_environment() == EnvironmentName.SLURM
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, "slrum")
    with pytest.raises(ValueError, match="slrum"):
        requested_environment()
    monkeypatch.delenv(ENVIRONMENT_VARIABLE)
    with pytest.raises(ValueError, match="not a valid"):
        requested_environment()
