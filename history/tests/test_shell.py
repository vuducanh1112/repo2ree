"""Integration contracts for filesystem boundaries and command dispatch."""

import json

import pytest
from history.tests.fixtures import make_execution

from repo2ree_history.core.evidence import AssemblyResult
from repo2ree_history.shell.cli import main
from repo2ree_history.shell.outputs import write_files, write_outputs
from repo2ree_history.shell.recording import load_recording


def test_loaded_snapshot_survives_removal_of_its_source(tmp_path):
    from repo2ree_history.core.assembly import assemble

    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "execution_id": "test",
                "nodeid": "test",
                "started": 0,
                "finished": 1,
                "repositories": [],
            }
        )
    )
    snapshot = load_recording(tmp_path)
    (tmp_path / "manifest.json").unlink()
    result = assemble(snapshot)
    assert not result.executions
    assert {item.code for item in result.diagnostics} == {"missing_artifact"}


def test_invalid_render_preserves_evidence_and_reports_failure(tmp_path):
    execution = make_execution()
    broken = execution.events[0].model_copy(update={"causes": (execution.events[-1].event_id,)})
    execution = execution.model_copy(update={"events": (broken, *execution.events[1:])})
    result = AssemblyResult(
        recording_root="/recording",
        artifacts=execution.artifacts,
        events=execution.events,
        executions=(execution,),
        unassigned=(),
        diagnostics=(),
    )
    output = tmp_path / "out"
    write_outputs(result, output)
    saved = AssemblyResult.model_validate_json((output / "assembly.json").read_text())
    assert saved.events == result.events
    assert any(d.code == "sequence_unavailable" and d.severity == "invalid" for d in saved.diagnostics)
    assert "causal_cycle" in (output / "evidence-report.md").read_text()


def test_output_paths_are_checked_before_any_file_is_written(tmp_path):
    with pytest.raises(ValueError, match="escapes recording root"):
        write_files(tmp_path, {"good.json": "{}", "../escape.json": "{}"})
    assert not (tmp_path / "good.json").exists()


def test_schema_cli_replaces_removed_example_command(tmp_path):
    destination = tmp_path / "schema.json"
    assert main(["schema", "--output", str(destination)]) == 0
    assert json.loads(destination.read_text())["title"] == "SystemExecution"


def test_cli_reports_missing_input_without_traceback(tmp_path, capsys):
    assert main(["assemble", str(tmp_path / "missing"), "--output", str(tmp_path / "out")]) == 1
    assert "history:" in capsys.readouterr().err


def test_cli_reports_git_failure_without_traceback(tmp_path, monkeypatch, capsys):
    from subprocess import CalledProcessError

    def fail(_path):
        raise CalledProcessError(128, ["git", "log"])

    monkeypatch.setattr("repo2ree_history.shell.cli.assemble_recording", fail)
    assert main(["assemble", str(tmp_path), "--output", str(tmp_path / "out")]) == 1
    assert "history:" in capsys.readouterr().err
