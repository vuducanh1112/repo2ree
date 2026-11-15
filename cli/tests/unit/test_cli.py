"""``ree`` as its callers use it: a person at a terminal, and a workbench reading ``--json``.

The workbench runs ``ree -C <root> --json …`` and depends on that contract: the ActionResult as one JSON line on
stdout, NDJSON log events on stderr, and the exit status. A person runs the same verbs and reads plain lines.
These tests drive the real command line, real handlers and a real REE tree in a temp directory.
"""

from __future__ import annotations

import io
import json
import os
import signal
import tarfile
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

import repo2ree_core.operations.session as session_module
from repo2ree_cli.cli import CANCELED, REFUSED, cli
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.reproduction.commands import REPRODUCTION_COMMANDS
from repo2ree_protocol.command import (
    ActivationTestCommand,
    BuildExperimentEnvironmentCommand,
    MaterializeWorkspaceCommand,
    RunExperimentCommand,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.verbs import SUMMARIES, VERBS
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

BUILD_SCRIPT = RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
runner = CliRunner()


def ree(root: Path, *words: str, input: str | bytes | None = None) -> Result:  # noqa: A002 — CliRunner's name
    return runner.invoke(cli, ["-C", str(root), *words], input=input)


def machine(root: Path, *words: str, input: str | bytes | None = None) -> Result:  # noqa: A002
    return ree(root, "--json", *words, input=input)


def _stderr_events(result: Result) -> list[dict]:  # type: ignore[type-arg]
    return [json.loads(line) for line in result.stderr.splitlines() if line.strip()]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "ree"


@pytest.fixture
def initialized(root: Path) -> Path:
    result = ree(root, "init", "--name", "demo")
    assert result.exit_code == 0, result.output
    return root


# ================================================
# init / manifest / build-info
# ================================================


def test_build_info_reports_injected_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO2REE_BUILD_REVISION", "cli-revision")

    result = runner.invoke(cli, ["build-info"])

    assert result.exit_code == 0
    assert json.loads(result.output)["revision"] == "cli-revision"


def test_init_bootstraps_tree_and_metadata(root: Path) -> None:
    result = ree(root, "init", "--name", "demo")
    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "initialised"
    assert json.loads(result.output)["snapshot_id"]

    layout = ReeLayout(root=root)
    assert layout.workspace.is_dir()
    metadata = json.loads(layout.manifest.read_text())
    assert metadata["subject"]["definition"]["name"] == "demo"
    assert "seal" not in metadata
    build = metadata["subject"]["definition"]["experiment_environment"]
    assert build["build_experiment_environment_script_path"] == BUILD_SCRIPT
    assert layout.overlay_file(BUILD_SCRIPT).is_file()
    assert layout.workspace_file(BUILD_SCRIPT).is_file()


def test_init_is_idempotent(initialized: Path) -> None:
    before = ReeLayout(root=initialized).manifest.read_text()

    result = ree(initialized, "init", "--name", "demo")
    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "already_initialised"
    assert ReeLayout(root=initialized).manifest.read_text() == before


def test_init_reports_capture_failure(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("repo2ree_core.persistence.history.find_tool", lambda name: None)
    result = ree(root, "init", "--name", "demo")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Git is required" in json.loads(result.stderr)["error"]
    assert not root.exists()


def test_init_seeds_the_scripts_of_its_environment(root: Path) -> None:
    result = ree(root, "init", "--name", "demo", "--workbench-environment", "host")

    assert result.exit_code == 0, result.output
    assert "docker" not in ReeDirectory(ReeLayout(root=root)).overlay.read_text(BUILD_SCRIPT)


def test_manifest_before_init_exits_nonzero(root: Path) -> None:
    result = ree(root, "manifest")
    assert result.exit_code == 1
    assert json.loads(result.stderr) == {"error": "not initialised"}


def test_manifest_prints_the_record(initialized: Path) -> None:
    result = ree(initialized, "manifest")
    assert result.exit_code == 0
    assert json.loads(result.output)["subject"]["definition"]["name"] == "demo"


def test_without_c_the_nearest_ree_above_the_current_directory_is_the_one(
    initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (initialized / "workspace" / "deep").mkdir(parents=True)
    monkeypatch.chdir(initialized / "workspace" / "deep")

    result = runner.invoke(cli, ["manifest"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["subject"]["definition"]["name"] == "demo"


# ================================================
# Commands, as the workbench runs them (--json)
# ================================================


def test_a_command_writes_its_result_to_stdout_and_its_logs_to_stderr(initialized: Path) -> None:
    result = machine(initialized, "--run-id", "run-1", "write", BUILD_SCRIPT, input="echo build\n")
    assert result.exit_code == 0, result.output

    assert ActionResult.model_validate_json(result.stdout.strip()).status == "succeeded"
    layout = ReeLayout(root=initialized)
    assert layout.overlay_file(BUILD_SCRIPT).read_text() == "echo build\n"
    assert layout.workspace_file(BUILD_SCRIPT).read_text() == "echo build\n"
    # stderr is NDJSON log events only: the workbench parses every line.
    events = _stderr_events(result)
    assert events
    assert all(event["type"] == "log" for event in events)
    frames = [json.loads(line) for line in layout.run_log("run-1").read_text().splitlines()]
    assert {frame["type"] for frame in frames} == {"command", "log", "result"}


def test_an_explicit_context_joins_the_result_the_logs_and_the_history(
    initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TRACE_RELAY", raising=False)
    context = ExecutionContext.new(ree_id="ree-1")

    invocation = machine(
        initialized, "--run-id", "reused-run", "--context", context.model_dump_json(), "write", BUILD_SCRIPT, input="x"
    )

    assert invocation.exit_code == 0, invocation.output
    result = ActionResult.model_validate_json(invocation.stdout)
    assert result.context == context
    assert result.history is not None
    layout = ReeLayout(root=initialized)
    record = read_operation_history(layout).operations[0]
    assert record.context == context
    assert record.after_snapshot_id == result.history.after_snapshot_id
    frames = [json.loads(line) for line in layout.run_log("reused-run").read_text().splitlines()]
    assert all(frame["context"] == context.model_dump(mode="json") for frame in frames)
    assert frames[-1]["result"]["history"] == result.history.model_dump(mode="json")


def test_the_run_log_records_the_whole_command_and_result_untruncated(initialized: Path) -> None:
    content = "echo build\n" + "x" * 4000
    result = machine(initialized, "--run-id", "run-2", "write", BUILD_SCRIPT, input=content)
    assert result.exit_code == 0, result.output

    frames = [json.loads(line) for line in ReeLayout(root=initialized).run_log("run-2").read_text().splitlines()]
    [command_frame] = [frame for frame in frames if frame["type"] == "command"]
    [result_frame] = [frame for frame in frames if frame["type"] == "result"]
    assert {frame["run_id"] for frame in frames} == {"run-2"}
    assert command_frame["command"]["args"]["content"] == content
    assert result_frame["result"]["status"] == "succeeded"
    assert frames.index(command_frame) == 0
    assert frames.index(result_frame) == len(frames) - 1


def test_words_that_spell_no_command_are_a_usage_error(initialized: Path) -> None:
    result = machine(initialized, "seal", "--no-such-option")
    assert result.exit_code == 2
    assert "takes no option --no-such-option" in result.output


def test_a_failing_command_still_reports_its_result(initialized: Path) -> None:
    result = machine(
        initialized,
        "acquire-source",
        "--mode",
        "download",
        "--origin-url",
        str(initialized / "does-not-exist"),
        "--source-type",
        "git",
    )
    assert result.exit_code in (1, REFUSED)
    assert ActionResult.model_validate_json(result.stdout.strip()).status == "failed"


def test_a_refused_command_exits_refused(initialized: Path) -> None:
    result = machine(initialized, "experiment", "missing")
    assert result.exit_code == REFUSED
    failure = ActionResult.model_validate_json(result.stdout.strip()).failure
    assert failure is not None
    assert failure.category == "precondition"


def test_cancel_writes_the_cancel_marker(initialized: Path) -> None:
    result = ree(initialized, "cancel", "run-1")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"status": "cancel_requested", "run_id": "run-1"}
    assert ReeLayout(root=initialized).run_cancel_marker("run-1").is_file()


def test_a_canceled_run_exits_canceled_and_clears_its_marker(initialized: Path) -> None:
    layout = ReeLayout(root=initialized)
    layout.run_cancel_marker("run-1").touch()

    result = machine(initialized, "--run-id", "run-1", "write", BUILD_SCRIPT, input="echo build\n")

    assert result.exit_code == CANCELED
    assert ActionResult.model_validate_json(result.stdout.strip()).status == "canceled"
    # The marker is the run's own: a later run reusing the id is not canceled by its leftover.
    assert not layout.run_cancel_marker("run-1").exists()


@pytest.mark.parametrize("stop", [signal.SIGTERM, signal.SIGINT])
def test_a_stop_signal_cancels_the_run_cooperatively_and_the_handler_is_restored(
    initialized: Path, monkeypatch: pytest.MonkeyPatch, stop: signal.Signals
) -> None:
    def interrupted(cmd, *, layout, runner, log, run_id, is_canceled, context):
        assert not is_canceled()
        os.kill(os.getpid(), stop)  # As the workbench escalates a cancel, or a person presses Ctrl-C.
        return ActionResult(status="canceled" if is_canceled() else "succeeded")

    monkeypatch.setattr(session_module, "run_command", interrupted)
    before = signal.getsignal(stop)

    result = machine(initialized, "--run-id", "run-1", "write", BUILD_SCRIPT, input="echo build\n")

    assert ActionResult.model_validate_json(result.stdout.strip()).status == "canceled"
    assert signal.getsignal(stop) is before


# ================================================
# Commands, as a person runs them
# ================================================


def test_a_person_reads_plain_lines_and_the_outcome(initialized: Path) -> None:
    result = ree(initialized, "write", BUILD_SCRIPT, input="echo build\n")

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "{" not in result.stderr
    assert result.stderr.strip().endswith("write succeeded")


def test_a_person_sees_why_a_command_was_refused(initialized: Path) -> None:
    result = ree(initialized, "experiment", "missing")

    assert result.exit_code == REFUSED
    assert "experiment failed:" in result.stderr


def test_an_archive_is_staged_and_acquired_as_an_upload(initialized: Path, tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "main.py").write_text("print('hello')\n")
    archive = tmp_path / "project.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname="project")

    result = ree(initialized, "acquire-source", "--archive", str(archive), "--source-type", "tarball")

    assert result.exit_code == 0, result.output
    layout = ReeLayout(root=initialized)
    assert layout.snapshot_archive.is_file()
    assert ReeDirectory(layout).read_ree().subject.definition.source is not None


def test_a_script_edited_in_place_is_picked_up_before_the_next_command(initialized: Path) -> None:
    layout = ReeLayout(root=initialized)
    layout.overlay_file(BUILD_SCRIPT).write_text("echo edited in my editor\n")

    result = ree(initialized, "materialize-workspace")

    assert "picking up the edit to " + BUILD_SCRIPT in result.stderr
    assert layout.workspace_file(BUILD_SCRIPT).read_text() == "echo edited in my editor\n"
    operations = [record.command["operation"] for record in read_operation_history(layout).operations]
    assert "write_file" in operations


def test_the_steps_shared_with_run_sh_have_its_names_and_its_summaries() -> None:
    shared = {step.name: step.summary for step in REPRODUCTION_COMMANDS}
    for command in (MaterializeWorkspaceCommand, BuildExperimentEnvironmentCommand, ActivationTestCommand):
        [verb] = VERBS[command]
        assert SUMMARIES[command] == shared[verb]
    assert VERBS[RunExperimentCommand] == ("experiment",)
    assert SUMMARIES[RunExperimentCommand] == shared["experiment"]


# ================================================
# Reading an REE
# ================================================


def test_cat_round_trips_workspace_bytes(initialized: Path) -> None:
    assert machine(initialized, "write", BUILD_SCRIPT, input="payload\n").exit_code == 0

    result = ree(initialized, "cat", f"workspace/{BUILD_SCRIPT}")
    assert result.exit_code == 0
    assert result.stdout_bytes == b"payload\n"


def test_cat_reads_outside_the_workspace(initialized: Path) -> None:
    ReeLayout(root=initialized).snapshot_archive.write_bytes(b"snapshot")

    result = ree(initialized, "cat", "--", "snapshot.tar.gz")

    assert result.exit_code == 0
    assert result.stdout_bytes == b"snapshot"


def test_cat_of_a_missing_file_exits_nonzero(initialized: Path) -> None:
    result = ree(initialized, "cat", "missing.txt")
    assert result.exit_code == 1
    assert "not found" in json.loads(result.stderr)["error"]


def test_cat_refuses_a_path_out_of_the_ree(initialized: Path) -> None:
    result = ree(initialized, "cat", "../outside")
    assert result.exit_code == 1
    assert json.loads(result.stderr)["error"] == "Invalid REE file path"


def test_show_reflects_workspace_files(initialized: Path) -> None:
    assert machine(initialized, "write", "ree-scripts/experiments/hello.sh", input="print('hi')\n").exit_code == 0

    result = ree(initialized, "show")
    assert result.exit_code == 0
    document = json.loads(result.output)
    # The command line knows only its REE's directory, not where a control plane keeps it.
    assert "ree_id" not in document
    assert any(f.get("path") == "ree-scripts/experiments/hello.sh" for f in document["workspace_files"])


def test_show_summary_omits_inline_file_content(initialized: Path) -> None:
    assert machine(initialized, "write", "ree-scripts/experiments/hello.sh", input="print('hi')\n").exit_code == 0

    result = ree(initialized, "show", "--summary")

    assert result.exit_code == 0
    document = json.loads(result.output)
    assert document["workspace_files"]
    assert all(file["content"] is None for file in document["workspace_files"])
    assert all(file["content"] is None for file in document["ree_files"])


def test_bundle_before_seal_writes_a_draft_bundle(initialized: Path) -> None:
    result = ree(initialized, "bundle")

    assert result.exit_code == 0
    with zipfile.ZipFile(io.BytesIO(result.stdout_bytes)) as archive:
        assert "ree/.git/HEAD" in archive.namelist()
        assert "ree.zip" not in archive.namelist()
        manifest = json.loads(archive.read("ree/ree.json"))
    assert "seal" not in manifest
