"""An experiment's scripts come and go with its declaration, starting as their defaults."""

from __future__ import annotations

from pathlib import Path

from repo2ree_authoring.templates import experiment_run_templates, experiment_verify_templates
from repo2ree_core.operations.handlers.author.patch_ree_definition import handle_patch_ree_definition
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import PatchReeDefinitionArgs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.reserved_paths import experiment_run_script_path, experiment_verify_script_path


def _patch(layout: ReeLayout, patch: dict[str, object]) -> ActionResult:
    return handle_patch_ree_definition(
        PatchReeDefinitionArgs(patch=patch), layout=layout, log=lambda *args: None, is_canceled=lambda: False
    )


def _initialized(tmp_path: Path) -> ReeLayout:
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="demo")
    return layout


def test_a_declared_experiment_starts_with_the_default_scripts_and_verifies_by_passing(tmp_path: Path) -> None:
    layout = _initialized(tmp_path)

    assert _patch(layout, {"experiments": [{"name": "fig one"}]}).status == "succeeded"

    store = ReeDirectory(layout)
    [experiment] = store.read_ree().subject.definition.experiments
    assert store.overlay.read_text(experiment_run_script_path("fig one")) == experiment_run_templates()[0].body
    assert store.overlay.read_text(experiment_verify_script_path("fig one")) == experiment_verify_templates()[0].body
    assert store.workspace.read_text(experiment_verify_script_path("fig one")) == experiment_verify_templates()[0].body
    assert experiment.verify_script_path == experiment_verify_script_path("fig one")


def test_an_experiment_renamed_takes_its_scripts_along(tmp_path: Path) -> None:
    layout = _initialized(tmp_path)
    store = ReeDirectory(layout)
    assert _patch(layout, {"experiments": [{"name": "old"}]}).status == "succeeded"
    store.overlay.write_text(experiment_run_script_path("old"), "echo old\n")

    renamed = {"name": "new", "run_script_path": experiment_run_script_path("old")}
    assert _patch(layout, {"experiments": [renamed]}).status == "succeeded"

    assert not store.overlay.is_file(experiment_run_script_path("old"))
    assert not store.workspace.is_file(experiment_verify_script_path("old"))
    assert store.overlay.read_text(experiment_run_script_path("new")) == "echo old\n"
    assert store.workspace.read_text(experiment_run_script_path("new")) == "echo old\n"


def test_an_experiment_replaced_by_another_takes_its_scripts_away(tmp_path: Path) -> None:
    layout = _initialized(tmp_path)
    store = ReeDirectory(layout)
    assert _patch(layout, {"experiments": [{"name": "old"}]}).status == "succeeded"
    store.overlay.write_text(experiment_run_script_path("old"), "echo old\n")

    assert _patch(layout, {"experiments": [{"name": "new"}]}).status == "succeeded"

    assert not store.overlay.is_file(experiment_run_script_path("old"))
    assert store.overlay.read_text(experiment_run_script_path("new")) == experiment_run_templates()[0].body


def test_a_refused_patch_leaves_the_scripts_as_they_were(tmp_path: Path) -> None:
    layout = _initialized(tmp_path)
    store = ReeDirectory(layout)
    assert _patch(layout, {"experiments": [{"name": "kept"}]}).status == "succeeded"
    store.overlay.write_text(experiment_run_script_path("kept"), "echo kept\n")

    refused = _patch(layout, {"experiments": [{"name": "added", "output_paths": ["../escape"]}]})

    assert refused.status == "failed"
    assert not store.overlay.is_file(experiment_run_script_path("added"))
    assert store.overlay.read_text(experiment_run_script_path("kept")) == "echo kept\n"
    assert [experiment.name for experiment in store.read_ree().subject.definition.experiments] == ["kept"]


def test_a_refused_rename_leaves_the_scripts_where_they_were(tmp_path: Path) -> None:
    layout = _initialized(tmp_path)
    store = ReeDirectory(layout)
    assert _patch(layout, {"experiments": [{"name": "old"}]}).status == "succeeded"
    store.overlay.write_text(experiment_run_script_path("old"), "echo old\n")

    renamed = {"name": "new", "run_script_path": experiment_run_script_path("old"), "output_paths": ["../escape"]}
    assert _patch(layout, {"experiments": [renamed]}).status == "failed"

    assert store.overlay.read_text(experiment_run_script_path("old")) == "echo old\n"
    assert not store.overlay.is_file(experiment_run_script_path("new"))
