"""Authoring an REE as a person and an agent do: where it stands, its definition, its scripts, and its reviews."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result

import repo2ree_cli.cli as cli_module
import repo2ree_core.operations.session as session_module
from repo2ree_authoring.templates import experiment_run_templates, verify_templates
from repo2ree_cli.cli import REFUSED, cli
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.document import ReeStatusReport
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

BUILD_SCRIPT = RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
PROJECT = Path(__file__).resolve().parents[3] / "examples/projects/instant/source"
runner = CliRunner()


def ree(root: Path, *words: str, input: str | None = None) -> Result:  # noqa: A002 — CliRunner's name
    return runner.invoke(cli, ["-C", str(root), *words], input=input)


def outputs(result: Result) -> dict[str, Any]:
    answered = ActionResult.model_validate_json(result.stdout)
    assert answered.status == "succeeded", result.output
    return answered.outputs


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "ree"
    assert ree(root, "initialize-ree", "--name", "demo").exit_code == 0
    return root


@pytest.fixture
def acquired(root: Path, tmp_path: Path) -> Path:
    archive = tmp_path / "project.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in PROJECT.iterdir():
            tar.add(path, arcname=path.name)
    result = ree(root, "acquire-source", "--archive", str(archive))
    assert result.exit_code == 0, result.output
    return root


def status(root: Path) -> ReeStatusReport:
    return ReeStatusReport.model_validate(outputs(ree(root, "--json", "status")))


# ================================================
# status
# ================================================


def test_status_tells_a_person_what_to_run_next(root: Path) -> None:
    result = ree(root, "status")

    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("demo (draft, revision sha256:")
    assert "→  1 Source Acquisition" in result.stdout
    assert "(needs Build Experiment Environment)" in result.stdout
    assert result.stdout.rstrip().endswith(
        "next: Source Acquisition: ree acquire-source --archive PATH, or ree acquire-source --origin-url URL"
    )


def test_status_gives_an_agent_the_revision_and_the_digest_of_each_script(root: Path) -> None:
    report = status(root)

    assert report.steps.next == "source"
    assert report.running is None
    build = next(script for script in report.scripts if script.kind == "build_experiment_environment")
    assert build.path == BUILD_SCRIPT
    assert build.etag is not None
    assert build.etag.startswith("sha256:")
    assert all(script.etag is not None for script in report.scripts if script.kind != "experiment_verify")


def test_a_guarded_write_names_the_digest_status_reports(root: Path) -> None:
    etag = next(script.etag for script in status(root).scripts if script.path == BUILD_SCRIPT)
    assert etag is not None

    written = ree(root, "write-script", "--expected-etag", etag, "build_experiment_environment", input="echo one\n")
    stale = ree(root, "--json", "write-script", "--expected-etag", etag, BUILD_SCRIPT, input="echo two\n")

    assert written.exit_code == 0, written.output
    assert stale.exit_code == REFUSED
    failure = ActionResult.model_validate_json(stale.stdout).failure
    assert failure is not None
    assert failure.category == "conflict"
    assert ReeLayout(root=root).overlay_file(BUILD_SCRIPT).read_text() == "echo one\n"


def test_a_refused_command_tells_a_person_what_to_run_next(root: Path) -> None:
    result = ree(root, "evaluate-reproducibility")

    assert result.exit_code == REFUSED
    assert "next: Source Acquisition: ree acquire-source" in result.stderr


# ================================================
# define
# ================================================


def test_define_changes_the_fields_it_is_given_and_keeps_the_rest(root: Path) -> None:
    assert ree(root, "patch-ree-definition", "--version", "1.0", "--description", "A hello world.").exit_code == 0

    result = ree(root, "patch-ree-definition", "--version", "1.1", "--keyword", "hello", "--keyword", "world")

    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("revision sha256:")
    catalog = ReeDirectory(ReeLayout(root=root)).read_ree().subject.definition.catalog
    assert (catalog.version, catalog.description, list(catalog.keywords)) == (
        "1.1",
        "A hello world.",
        ["hello", "world"],
    )


def test_define_declares_an_experiment_with_its_scripts_and_removes_them_with_it(root: Path) -> None:
    layout = ReeLayout(root=root)
    run, verify = (
        layout.overlay_file("ree-scripts/experiments/fig.sh"),
        layout.overlay_file("ree-scripts/experiments/fig.verify.sh"),
    )
    undeclared = ree(root, "write-script", "experiment_run:fig", input="echo hi > out.txt\n")
    assert undeclared.exit_code == REFUSED
    assert "declare its experiment first" in undeclared.stderr

    assert ree(root, "patch-ree-definition", "--experiment", "fig", "--output", "out.txt").exit_code == 0
    assert (run.read_text(), verify.read_text()) == (experiment_run_templates()[0].body, verify_templates()[0].body)
    assert ree(root, "write-script", "experiment_run:fig", input="echo hi > out.txt\n").exit_code == 0
    assert ree(root, "patch-ree-definition", "--experiment", "fig", "--output", "out.csv").exit_code == 0

    [experiment] = ReeDirectory(layout).read_ree().subject.definition.experiments
    assert (experiment.name, [str(path) for path in experiment.output_paths]) == ("fig", ["out.csv"])
    assert experiment.verify_script_path == "ree-scripts/experiments/fig.verify.sh"
    assert run.read_text() == "echo hi > out.txt\n"
    assert ree(root, "patch-ree-definition", "--remove-experiment", "fig").exit_code == 0
    assert not ReeDirectory(layout).read_ree().subject.definition.experiments
    assert not run.exists()
    assert not verify.exists()


def test_define_still_takes_a_json_patch_on_stdin(root: Path) -> None:
    result = ree(root, "patch-ree-definition", input=json.dumps({"name": "renamed"}))

    assert result.exit_code == 0, result.output
    assert ReeDirectory(ReeLayout(root=root)).read_ree().subject.definition.name == "renamed"


def test_an_output_names_the_experiment_it_follows(root: Path) -> None:
    result = ree(root, "patch-ree-definition", "--output", "out.txt")

    assert result.exit_code == REFUSED
    assert "--output names a path of the --experiment it follows" in result.stderr


# ================================================
# infer --write
# ================================================


def test_infer_shows_each_proposal_against_the_script_as_written(acquired: Path) -> None:
    result = ree(acquired, "suggest-scripts", "--target", "build_experiment_environment")

    assert result.exit_code == 0, result.output
    assert f"{BUILD_SCRIPT}: needs input" in result.stdout
    assert "rule root-pip-requirements-v1" in result.stdout
    assert "--- written" in result.stdout


def test_infer_writes_the_proposed_script(acquired: Path) -> None:
    result = ree(acquired, "--json", "suggest-scripts", "--target", "build_experiment_environment", "--write")

    assert result.exit_code == 0, result.output
    written = outputs(result)
    assert written["path"] == BUILD_SCRIPT
    assert written["rule"] == "root-pip-requirements-v1"
    assert "Inference rule: root-pip-requirements-v1" in ReeLayout(root=acquired).overlay_file(BUILD_SCRIPT).read_text()


def test_infer_refuses_to_write_what_no_rule_proposes(acquired: Path) -> None:
    before = ReeLayout(root=acquired).overlay_file(BUILD_SCRIPT).read_text()

    result = ree(acquired, "suggest-scripts", "--target", "build_experiment_environment", "--write", "--rule", "nope")

    assert result.exit_code == REFUSED
    assert f"inference proposes no script for {BUILD_SCRIPT} by rule nope" in result.stderr
    assert ReeLayout(root=acquired).overlay_file(BUILD_SCRIPT).read_text() == before


def test_infer_writes_one_script_at_a_time(root: Path) -> None:
    result = ree(root, "suggest-scripts", "--target", "launch", "--target", "check_working_environment", "--write")

    assert result.exit_code == REFUSED
    assert "--write writes one script" in result.stderr


# ================================================
# edit
# ================================================


def test_edit_writes_what_the_editor_saved(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "_at_terminal", lambda: True)
    opened: list[str | None] = []

    def editor(text: str | None = None, **_kwargs: Any) -> str:
        opened.append(text)
        return "echo edited\n"

    monkeypatch.setattr("click.edit", editor)

    assert ree(root, "patch-ree-definition", "--experiment", "fig").exit_code == 0
    result = ree(root, "edit", "experiment_run:fig")

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "wrote ree-scripts/experiments/fig.sh"
    assert opened[0] == experiment_run_templates()[0].body
    assert ReeLayout(root=root).overlay_file("ree-scripts/experiments/fig.sh").read_text() == "echo edited\n"


def test_edit_that_changes_nothing_writes_nothing(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "_at_terminal", lambda: True)
    monkeypatch.setattr("click.edit", lambda text=None, **_kwargs: text)

    result = ree(root, "edit", "build_experiment_environment")

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == f"{BUILD_SCRIPT} unchanged"


def test_edit_needs_a_terminal(root: Path) -> None:
    result = ree(root, "--json", "edit", "build_experiment_environment")

    assert result.exit_code == REFUSED
    failure = ActionResult.model_validate_json(result.stdout).failure
    assert failure is not None
    assert "edit needs a terminal" in failure.message


# ================================================
# review
# ================================================


def _ran(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Record each command a session runs instead of running it."""
    ran: list[Any] = []

    def run_command(cmd: Any, **_kwargs: Any) -> ActionResult:
        ran.append(cmd)
        return ActionResult(status="succeeded")

    monkeypatch.setattr(session_module, "run_command", run_command)
    return ran


def test_a_review_step_without_a_review_is_refused(root: Path) -> None:
    result = ree(root, "review", "activate-experiment-environment")

    assert result.exit_code == REFUSED
    assert "no review yet: open one with `ree review acquire-source`" in result.stderr


def test_acquiring_a_review_source_opens_a_review_of_its_own(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran = _ran(monkeypatch)

    assert ree(root, "review", "acquire-source", "--basis", "bundled").exit_code == 0

    [opened] = ran
    assert opened.operation == "review_acquire_source"
    assert opened.args.review_id.startswith("review-")
    assert opened.args.basis == "bundled"


def test_review_all_runs_every_step_in_one_review(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert ree(root, "patch-ree-definition", "--experiment", "fig").exit_code == 0
    assert ree(root, "write-script", "experiment_run:fig", input="echo hi\n").exit_code == 0
    ran = _ran(monkeypatch)

    result = ree(root, "--json", "review", "all", "--basis", "independent")

    assert result.exit_code == 0, result.output
    assert [cmd.operation for cmd in ran] == [
        "review_acquire_source",
        "review_build_experiment_environment",
        "review_activate_experiment_environment",
        "review_run_experiment",
    ]
    assert len({cmd.args.review_id for cmd in ran}) == 1
    assert ran[1].args.basis == "independent"
    assert [step["words"] for step in outputs(result)["steps"]][-1] == ["review", "run-experiment", "fig"]


def test_review_all_stops_at_the_first_step_that_fails(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[Any] = []

    def run_command(cmd: Any, **_kwargs: Any) -> ActionResult:
        ran.append(cmd)
        if cmd.operation == "review_build_experiment_environment":
            return ActionResult.failed("execution", "the build failed")
        return ActionResult(status="succeeded")

    monkeypatch.setattr(session_module, "run_command", run_command)

    result = ree(root, "--json", "review", "all")

    assert result.exit_code == 1
    assert len(ran) == 2
    answered = ActionResult.model_validate_json(result.stdout)
    assert answered.failure is not None
    assert answered.failure.message == "the build failed"
    assert [step["status"] for step in answered.outputs["steps"]] == ["succeeded", "failed"]


# ================================================
# schema and completion
# ================================================


def test_schema_describes_every_command_a_person_sees(root: Path) -> None:
    result = ree(root, "--json", "schema")

    assert result.exit_code == 0, result.output
    described = json.loads(result.stdout)
    words = {" ".join(command["words"]) for command in described["commands"]}
    assert {
        "status",
        "write-script",
        "patch-ree-definition",
        "suggest-scripts",
        "review all",
        "review run-experiment",
        "seal-ree",
        "cat",
    } <= words
    assert not {"settle", "build-info", "lint-draft", "manifest"} & words
    assert described["exit_codes"]["2"].startswith("refused")
    assert "precondition" in described["failure_categories"]


def test_schema_of_one_command_says_its_stdin_options_and_outputs(root: Path) -> None:
    [write] = json.loads(ree(root, "--json", "schema", "write-script").stdout)["commands"]
    [review_step] = json.loads(ree(root, "--json", "schema", "review", "acquire-source").stdout)["commands"]
    [cat] = json.loads(ree(root, "--json", "schema", "cat").stdout)["commands"]

    assert write["stdin"] == {"field": "content", "format": "text", "description": "The script."}
    assert write["runs"] is True
    assert {"name": "--expected-etag", "kind": "option"}.items() <= write["params"][0].items()
    basis = next(param for param in review_step["params"] if param["name"] == "--basis")
    assert basis["choices"] == ["auto", "independent", "bundled"]
    assert cat["stdout"] == "bytes"


def test_schema_of_no_command_is_refused(root: Path) -> None:
    assert ree(root, "schema", "no-such").exit_code == REFUSED


def test_completion_prints_the_shell_script() -> None:
    result = runner.invoke(cli, ["completion", "bash"])

    assert result.exit_code == 0, result.output
    assert "_REE_COMPLETE" in result.stdout
