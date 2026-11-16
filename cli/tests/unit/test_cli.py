"""``ree`` as its callers use it: a person at a terminal, and a workbench reading ``--json``.

The workbench runs ``ree -C <root> --json …`` and depends on that contract: the ActionResult as one JSON line on
stdout, NDJSON log events on stderr, and the exit status. A person runs the same verbs and reads plain lines.
These tests drive the real command line, real handlers and a real REE tree in a temp directory.
"""

from __future__ import annotations

import fcntl
import io
import json
import os
import signal
import tarfile
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

import repo2ree_cli.cli as cli_module
import repo2ree_core.operations.session as session_module
from repo2ree_cli.cli import CANCELED, REFUSED, cli
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.persistence.run_lock import RUN_LOCK
from repo2ree_core.reproduction.commands import REPRODUCTION_COMMANDS
from repo2ree_protocol.command import (
    ActivationTestCommand,
    BuildExperimentEnvironmentCommand,
    MaterializeWorkspaceCommand,
    RunExperimentCommand,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.queries import InitRee, query_types, verb_of
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


def outputs(result: Result) -> dict:  # type: ignore[type-arg]
    """The outputs of the one result line ``--json`` prints, which must have succeeded."""
    answered = ActionResult.model_validate_json(result.stdout)
    assert answered.status == "succeeded", result.output
    return answered.outputs


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

    result = runner.invoke(cli, ["--json", "build-info"])

    assert result.exit_code == 0
    assert outputs(result)["revision"] == "cli-revision"


def test_init_bootstraps_tree_and_metadata(root: Path) -> None:
    result = machine(root, "init", "--name", "demo")
    assert result.exit_code == 0
    assert outputs(result)["state"] == "initialised"
    assert outputs(result)["snapshot_id"]

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

    result = machine(initialized, "init", "--name", "demo")
    assert result.exit_code == 0
    assert outputs(result)["state"] == "already_initialised"
    assert ReeLayout(root=initialized).manifest.read_text() == before


def test_init_reports_capture_failure(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("repo2ree_core.persistence.history.find_tool", lambda name: None)
    result = ree(root, "init", "--name", "demo")
    assert result.exit_code == REFUSED
    assert result.stdout == ""
    assert "init failed: Git is required" in result.stderr
    assert not root.exists()


def test_init_names_the_ree_after_its_directory(root: Path) -> None:
    result = ree(root, "init")

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [f"initialised {root}", "next: ree status"]
    assert ReeDirectory(ReeLayout(root=root)).read_ree().subject.definition.name == "ree"


def test_init_seeds_scripts_that_need_no_container_engine_and_a_check_that_passes(root: Path) -> None:
    result = ree(root, "init", "--name", "demo")

    assert result.exit_code == 0, result.output
    store = ReeDirectory(ReeLayout(root=root))
    assert "docker" not in store.overlay.read_text(BUILD_SCRIPT)
    assert store.read_ree().subject.definition.check_working_environment is not None
    checked = ree(root, "check-working-environment")
    assert checked.exit_code == 0, checked.output


def test_machine_says_what_ree_runs_on() -> None:
    result = runner.invoke(cli, ["--json", "machine"])

    assert result.exit_code == 0, result.output
    assert outputs(result)["arch"]


def test_a_read_before_init_is_refused(root: Path) -> None:
    result = machine(root, "show")

    assert result.exit_code == REFUSED
    refused = ActionResult.model_validate_json(result.stdout)
    assert refused.failure is not None
    assert refused.failure.category == "precondition"
    assert refused.failure.message == f"no REE at {root}: create one with `ree -C {root} init`"


def test_a_command_outside_any_ree_is_refused_and_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli, ["evaluate"])

    assert result.exit_code == REFUSED
    assert f"evaluate failed: no REE at or above {tmp_path}" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_a_workbench_reads_the_refusal_of_a_command_on_no_ree(root: Path) -> None:
    result = machine(root, "evaluate")

    assert result.exit_code == REFUSED
    refused = ActionResult.model_validate_json(result.stdout)
    assert refused.failure is not None
    assert refused.failure.category == "precondition"
    assert not root.exists()


def test_manifest_prints_the_record(initialized: Path) -> None:
    result = machine(initialized, "manifest")
    assert result.exit_code == 0
    assert outputs(result)["subject"]["definition"]["name"] == "demo"


def test_without_c_the_nearest_ree_above_the_current_directory_is_the_one(
    initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (initialized / "workspace" / "deep").mkdir(parents=True)
    monkeypatch.chdir(initialized / "workspace" / "deep")

    result = runner.invoke(cli, ["--json", "manifest"])

    assert result.exit_code == 0, result.output
    assert outputs(result)["subject"]["definition"]["name"] == "demo"


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
    # stderr is NDJSON events only, the run's id first: the workbench parses every line.
    events = _stderr_events(result)
    assert events[0] == {"type": "started", "run_id": "run-1", "operation": "write_file"}
    assert all(event["type"] == "log" for event in events[1:])
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


def test_words_that_spell_no_command_are_refused_as_a_result_under_json(initialized: Path) -> None:
    result = machine(initialized, "seal", "--no-such-option")

    assert result.exit_code == REFUSED
    refused = ActionResult.model_validate_json(result.stdout)
    assert refused.failure is not None
    assert refused.failure.category == "validation"
    assert "No such option: --no-such-option" in refused.failure.message


def test_a_person_is_shown_a_usage_error_with_the_usage(initialized: Path) -> None:
    result = ree(initialized, "review", "acquire-source", "--basis", "nope")

    assert result.exit_code == REFUSED
    assert "review acquire-source [OPTIONS]" in result.stderr
    assert "'nope' is not one of 'auto', 'independent', 'bundled'" in result.stderr


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
    result = machine(initialized, "cancel", "run-1")
    assert result.exit_code == 0, result.output
    assert outputs(result) == {"run_id": "run-1"}
    assert ReeLayout(root=initialized).run_cancel_marker("run-1").is_file()


def test_cancel_without_a_run_asks_the_running_one_and_refuses_when_none_runs(initialized: Path) -> None:
    assert ree(initialized, "cancel").exit_code == REFUSED
    layout = ReeLayout(root=initialized)
    with (layout.git_dir / RUN_LOCK).open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        held.write("run-busy")
        held.flush()

        result = ree(initialized, "cancel")

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "asked run run-busy to stop"
    assert layout.run_cancel_marker("run-busy").is_file()


def test_wait_returns_at_once_when_nothing_runs_and_gives_up_after_its_timeout(initialized: Path) -> None:
    assert outputs(machine(initialized, "wait")) == {"held_by": None}
    with (ReeLayout(root=initialized).git_dir / RUN_LOCK).open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        held.write("run-busy")
        held.flush()

        result = machine(initialized, "wait", "--timeout", "0.2")

    assert result.exit_code == 1
    failure = ActionResult.model_validate_json(result.stdout).failure
    assert failure is not None
    assert failure.category == "timeout"
    assert "run-busy" in failure.message


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
    def interrupted(cmd, *, layout, log, run_id, is_canceled, context):
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


def test_cat_of_a_missing_file_is_refused(initialized: Path) -> None:
    result = ree(initialized, "cat", "missing.txt")
    assert result.exit_code == REFUSED
    assert result.stdout == ""
    assert "cat failed: not found: missing.txt" in result.stderr


def test_cat_refuses_a_path_out_of_the_ree_as_a_result_under_json(initialized: Path) -> None:
    result = machine(initialized, "cat", "../outside")
    assert result.exit_code == REFUSED
    failure = ActionResult.model_validate_json(result.stdout).failure
    assert failure is not None
    assert failure.message == "Invalid REE file path"


def test_show_reflects_workspace_files(initialized: Path) -> None:
    assert machine(initialized, "write", "ree-scripts/experiments/hello.sh", input="print('hi')\n").exit_code == 0

    result = machine(initialized, "show")
    assert result.exit_code == 0
    document = outputs(result)
    # The command line knows only its REE's directory, not where a control plane keeps it.
    assert "ree_id" not in document
    assert any(f.get("path") == "ree-scripts/experiments/hello.sh" for f in document["workspace_files"])


def test_show_summary_omits_inline_file_content(initialized: Path) -> None:
    assert machine(initialized, "write", "ree-scripts/experiments/hello.sh", input="print('hi')\n").exit_code == 0

    result = machine(initialized, "show", "--summary")

    assert result.exit_code == 0
    document = outputs(result)
    assert document["workspace_files"]
    assert all(file["content"] is None for file in document["workspace_files"])
    assert all(file["content"] is None for file in document["ree_files"])


def test_a_person_reads_the_ree_as_a_summary(initialized: Path) -> None:
    result = ree(initialized, "show")

    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("demo (draft)\n")
    assert "source: none" in result.stdout
    assert "  activation: missing" in result.stdout


def test_a_person_reads_the_log_one_attempt_a_line(initialized: Path) -> None:
    assert ree(initialized, "write", BUILD_SCRIPT, input="echo build\n").exit_code == 0

    result = ree(initialized, "log")

    assert result.exit_code == 0, result.output
    [line] = [line for line in result.stdout.splitlines() if "write_file" in line]
    assert "succeeded" in line


def test_bundle_before_seal_writes_a_draft_bundle(initialized: Path) -> None:
    result = ree(initialized, "bundle")

    assert result.exit_code == 0
    with zipfile.ZipFile(io.BytesIO(result.stdout_bytes)) as archive:
        assert "ree/.git/HEAD" in archive.namelist()
        assert "ree.zip" not in archive.namelist()
        manifest = json.loads(archive.read("ree/ree.json"))
    assert "seal" not in manifest


def test_every_read_a_workbench_can_be_sent_is_a_command() -> None:
    assert {*(verb_of(read) for read in query_types()), verb_of(InitRee)} <= set(cli.commands)


# ================================================
# seal
# ================================================


def test_a_person_at_a_terminal_confirms_a_seal_seeing_what_is_not_complete(
    initialized: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "_at_terminal", lambda: True)

    declined = ree(initialized, "seal", input="n\n")

    assert declined.exit_code == 1
    assert "Not complete: Source Acquisition" in declined.stderr
    assert ReeDirectory(ReeLayout(root=initialized)).read_ree().seal is None

    confirmed = ree(initialized, "seal", input="y\n")

    assert confirmed.exit_code == 0, confirmed.output
    assert ReeDirectory(ReeLayout(root=initialized)).read_ree().seal is not None


def test_a_workbench_seals_without_being_asked(initialized: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "_at_terminal", lambda: True)

    result = machine(initialized, "seal")

    assert result.exit_code == 0, result.output
    assert ActionResult.model_validate_json(result.stdout).status == "succeeded"
