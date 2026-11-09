"""Every project is laid out alike."""

from typing import get_args

import pytest

from repo2ree_testbed.showcases import ALL_PROJECTS, PROJECTS, Project, ProjectName, RecipeScript


@pytest.mark.parametrize("project", ALL_PROJECTS, ids=lambda project: project.name)
def test_a_project_is_a_source_tree_beside_its_recipe(project: Project) -> None:
    assert any(project.source.iterdir())
    for script in get_args(RecipeScript):
        if script != "build_script.sh" or not project.infer_build:
            assert project.recipe(script)


def test_every_project_folder_is_defined() -> None:
    assert {path.name for path in PROJECTS.iterdir() if path.is_dir()} == set(ProjectName)
    assert {project.name for project in ALL_PROJECTS} == set(ProjectName)
