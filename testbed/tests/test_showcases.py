"""Every project is laid out alike, and every showcase has its machine and a test of each workflow."""

import subprocess
from typing import get_args

import pytest

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.runs.api_showcase import RUNNERS, e2e_arguments
from repo2ree_testbed.showcases import (
    ALL_PROJECTS,
    API_FEATURES,
    API_SUITE,
    API_TIER,
    CHECK,
    CLI_TIER,
    FEATURES,
    FEATURES_ENVIRONMENT,
    GUI_SHOWCASES,
    GUI_SUITE,
    PROJECTS,
    REQUIRED_SCRIPTS,
    SHOWCASES,
    Project,
    ProjectName,
    ShowcaseName,
    Workflow,
    api_suite,
    api_suites,
    api_test,
    environments_in_use,
    gui_machines,
    machine_of,
)
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName


@pytest.mark.parametrize("name", list(ShowcaseName))
@pytest.mark.parametrize("workflow", get_args(Workflow))
def test_a_showcase_has_an_api_test_of_each_workflow(name: ShowcaseName, workflow: Workflow) -> None:
    assert api_test(name, workflow).is_file()


@pytest.mark.parametrize("project", ALL_PROJECTS, ids=lambda project: project.name)
def test_a_project_is_a_source_tree_beside_a_recipe_for_each_script_it_does_not_infer(project: Project) -> None:
    assert any(project.source.iterdir())
    for script in REQUIRED_SCRIPTS:
        if project.rule(script) is None:
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
@pytest.mark.parametrize("workflow", get_args(Workflow))
def test_a_showcases_tests_run_on_its_machine(name: ShowcaseName, workflow: Workflow) -> None:
    node = f"{api_test(name, workflow).relative_to(ROOT)}::test_something"
    assert machine_of(node) == SHOWCASES[name].environment


def test_the_feature_tests_run_on_the_features_machine() -> None:
    node = f"{(API_FEATURES / 'test_origins.py').relative_to(ROOT)}::test_a_tarball_origin_is_fetched"
    assert machine_of(node) == FEATURES_ENVIRONMENT


def test_a_test_outside_the_api_showcases_has_no_machine() -> None:
    with pytest.raises(ValueError, match="no test of an API showcase"):
        machine_of("testbed/suites/system/test_authoring.py::test_something")
    with pytest.raises(ValueError, match="no test of an API showcase"):
        machine_of(f"{API_SUITE.relative_to(ROOT)}/conftest.py::test_something")


def test_one_run_holds_every_api_showcase_and_the_features() -> None:
    assert set(api_suites()) == {api_suite(name) for name in ShowcaseName} | {API_FEATURES}
    assert set(environments_in_use()) == {
        EnvironmentName.BARE,
        EnvironmentName.DOCKER,
        EnvironmentName.PODMAN,
        EnvironmentName.SLURM,
    }


def test_the_tiers_run_places_its_tests_itself() -> None:
    assert e2e_arguments(jobs=4, select=("a", "b"))[2:] == [
        *("--tier", API_TIER),
        *("--per-test", "--exit-on", "tests"),
        *("--jobs", "4"),
        *("--select", "a b"),
    ]
    assert "--environment" not in e2e_arguments(jobs=4)
    assert "--select" not in e2e_arguments(jobs=4)


def test_every_browser_showcase_spec_is_a_showcase_or_a_feature() -> None:
    named = [spec for workflows in GUI_SHOWCASES.values() for spec in workflows.values()]
    named += [feature.gui for feature in FEATURES.values() if feature.gui]
    assert sorted(named) == sorted(path.name for path in GUI_SUITE.glob("*.spec.ts"))
    assert all(feature.api is None or feature.api.is_file() for feature in FEATURES.values())


def test_the_showcase_tiers_have_their_recipes() -> None:
    recipes = subprocess.run(["just", "--summary"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
    assert f"test-{API_TIER}" in recipes
    assert f"test-{CLI_TIER}" in recipes


def test_the_cli_tier_runs_the_same_tests_through_its_own_runner() -> None:
    api, cli = e2e_arguments(jobs=1), e2e_arguments(jobs=1, surface="cli")
    assert (api[1], cli[1]) == (str(RUNNERS["api"]), str(RUNNERS["cli"]))
    assert all(runner.is_file() for runner in RUNNERS.values())
    assert cli[2:4] == ["--tier", CLI_TIER]


def test_every_project_checks_what_its_scripts_need() -> None:
    for project in ALL_PROJECTS:
        assert project.recipe(CHECK).startswith("#!/usr/bin/env sh\n"), project.name


def test_a_browser_spec_whose_scripts_call_docker_runs_on_a_machine_with_a_daemon_of_its_own() -> None:
    placed = gui_machines()
    assert all(spec.is_file() for spec in placed)
    assert placed[GUI_SUITE / "python-docker.spec.ts"] == EnvironmentName.DOCKER
    assert placed[GUI_SUITE / "java-maven.spec.ts"] == EnvironmentName.DOCKER
    assert placed[GUI_SUITE.parent / "e2e-instant/docker-authoring.spec.ts"] == EnvironmentName.DOCKER
