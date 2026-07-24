"""The executor CLI contract, exercised without a container.

The supervisor drives ``repo2ree-exec`` over ``docker exec`` and depends on
its process contract: ActionResult JSON on stdout, NDJSON log events on
stderr, and meaningful exit codes. These tests pin that contract with the
real CLI, real handlers, and a real REE tree — the only seam is redirecting
``WORKBENCH_ROOT`` to a temp dir, the same trick the core lifecycle flow test
uses. The in-container composition is covered by the supervisor e2e.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

import repo2ree_core.storage.layout as layout_mod
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_executor.cli import cli
from repo2ree_protocol.command import WriteFileArgs, WriteFileCommand
from repo2ree_protocol.result import ActionResult

# ================================================
# Fixtures / helpers
# ================================================


runner = CliRunner()


@pytest.fixture
def ree_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the workbench mount at a temp dir; commands resolve it at call time."""
    root = tmp_path / "ree"
    monkeypatch.setattr(layout_mod, "WORKBENCH_ROOT", root)
    return root


@pytest.fixture
def initialized_ree(ree_root: Path) -> Path:
    result = runner.invoke(cli, ["init-ree", "--ree-id", "abc123", "--name", "demo"])
    assert result.exit_code == 0, result.output
    return ree_root


def _stderr_events(result) -> list[dict]:  # type: ignore[type-arg]
    return [json.loads(line) for line in result.stderr.splitlines() if line.strip()]


# ================================================
# init-ree / get-ree
# ================================================


def test_init_ree_bootstraps_tree_and_metadata(ree_root: Path) -> None:
    result = runner.invoke(cli, ["init-ree", "--ree-id", "abc123", "--name", "demo"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"status": "initialised", "ree_id": "abc123"}

    layout = ReeLayout.in_workbench()
    assert layout.workspace.is_dir()
    metadata = json.loads(layout.metadata.read_text())
    assert metadata["ree_id"] == "abc123"
    assert metadata["name"] == "demo"
    assert metadata["status"] == "draft"
    # The build script is no longer carried on the intent; it is seeded as a
    # reserved, REE-owned overlay script (mirrored into the workspace).
    assert "build_runtime_script" not in metadata["ree_intent"]
    assert layout.overlay_file(RESERVED_BUILD_SCRIPT).is_file()
    assert layout.workspace_file(RESERVED_BUILD_SCRIPT).is_file()


def test_init_ree_is_idempotent(initialized_ree: Path) -> None:
    layout = ReeLayout.in_workbench()
    before = layout.metadata.read_text()

    result = runner.invoke(cli, ["init-ree", "--ree-id", "abc123"])
    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "already_initialised"
    assert layout.metadata.read_text() == before


def test_get_ree_before_init_exits_nonzero(ree_root: Path) -> None:
    result = runner.invoke(cli, ["get-ree"])
    assert result.exit_code == 1
    assert json.loads(result.stderr) == {"error": "not initialised"}


def test_get_ree_emits_metadata(initialized_ree: Path) -> None:
    result = runner.invoke(cli, ["get-ree"])
    assert result.exit_code == 0
    assert json.loads(result.output)["ree_id"] == "abc123"


def test_get_scorecard_before_init_exits_nonzero(ree_root: Path) -> None:
    result = runner.invoke(cli, ["get-scorecard"])
    assert result.exit_code == 1
    assert json.loads(result.stderr) == {"error": "not initialised"}


def test_get_scorecard_emits_camel_case_card(initialized_ree: Path) -> None:
    result = runner.invoke(cli, ["get-scorecard"])
    assert result.exit_code == 0
    card = json.loads(result.output)
    assert card["level_code"] == "R0"
    assert [category["key"] for category in card["categories"]] == [
        "source",
        "runtime",
        "activation",
        "experiments",
        "results",
    ]


# ================================================
# execute — the supervisor's dispatch contract
# ================================================


def test_execute_writes_result_to_stdout_and_logs_to_stderr(initialized_ree: Path) -> None:
    cmd = WriteFileCommand(args=WriteFileArgs(path="build.sh", content="echo build\n"))
    result = runner.invoke(cli, ["execute", "--action", "-", "--run-id", "run-1"], input=cmd.model_dump_json())
    assert result.exit_code == 0, result.output

    # stdout carries exactly one ActionResult JSON line
    action_result = ActionResult.model_validate_json(result.stdout.strip())
    assert action_result.status == "succeeded"

    # the file landed in overlay and workspace for real
    layout = ReeLayout.in_workbench()
    assert (layout.overlay / "build.sh").read_text() == "echo build\n"
    assert (layout.workspace / "build.sh").read_text() == "echo build\n"

    # stderr is pure NDJSON log events (the supervisor parses every line)
    events = _stderr_events(result)
    assert events
    assert all(event["type"] == "log" for event in events)

    # --run-id also appends the events + result to the durable run log
    run_log_lines = [json.loads(line) for line in layout.run_log("run-1").read_text().splitlines()]
    assert {"type": "result"} in run_log_lines


def test_execute_invalid_action_json_exits_2_with_ndjson_error(ree_root: Path) -> None:
    result = runner.invoke(cli, ["execute", "--action", "-"], input="not json")
    assert result.exit_code == 2
    [event] = _stderr_events(result)
    assert event["type"] == "log"
    assert event["level"] == "error"
    assert "invalid action JSON" in event["message"]


def test_execute_failing_command_exits_1_with_failed_result(initialized_ree: Path) -> None:
    """A command that fails still emits its ActionResult before exiting non-zero."""
    cmd = json.dumps(
        {
            "operation": "acquire_source",
            "args": {
                "origin_url": str(initialized_ree / "does-not-exist"),
                "source_type": "git",
            },
        }
    )
    result = runner.invoke(cli, ["execute", "--action", "-"], input=cmd)
    assert result.exit_code == 1
    action_result = ActionResult.model_validate_json(result.stdout.strip())
    assert action_result.status == "failed"


def test_cancel_run_writes_cancel_marker(initialized_ree: Path) -> None:
    result = runner.invoke(cli, ["cancel-run", "--run-id", "run-1"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"status": "cancel_requested", "run_id": "run-1"}
    assert ReeLayout.in_workbench().run_cancel_marker("run-1").is_file()


def test_execute_observes_existing_cancel_marker(initialized_ree: Path) -> None:
    layout = ReeLayout.in_workbench()
    layout.run_cancel_marker("run-1").touch()
    cmd = WriteFileCommand(args=WriteFileArgs(path="build.sh", content="echo build\n"))

    result = runner.invoke(cli, ["execute", "--action", "-", "--run-id", "run-1"], input=cmd.model_dump_json())

    assert result.exit_code == 1
    action_result = ActionResult.model_validate_json(result.stdout.strip())
    assert action_result.status == "canceled"


def test_execute_clears_cancel_marker_after_run(initialized_ree: Path) -> None:
    layout = ReeLayout.in_workbench()
    layout.run_cancel_marker("run-1").touch()
    cmd = WriteFileCommand(args=WriteFileArgs(path="build.sh", content="echo build\n"))

    runner.invoke(cli, ["execute", "--action", "-", "--run-id", "run-1"], input=cmd.model_dump_json())

    # The marker is self-contained: once the run it belongs to is done, a run
    # that later reuses the id must not be canceled by its leftover.
    assert not layout.run_cancel_marker("run-1").exists()


# ================================================
# Read-side queries
# ================================================


def test_read_file_round_trips_bytes(initialized_ree: Path) -> None:
    cmd = WriteFileCommand(args=WriteFileArgs(path="data.txt", content="payload\n"))
    assert runner.invoke(cli, ["execute", "--action", "-"], input=cmd.model_dump_json()).exit_code == 0

    result = runner.invoke(cli, ["read-file", "--path", "data.txt"])
    assert result.exit_code == 0
    assert result.stdout_bytes == b"payload\n"


def test_read_file_missing_exits_nonzero(initialized_ree: Path) -> None:
    result = runner.invoke(cli, ["read-file", "--path", "missing.txt"])
    assert result.exit_code == 1
    assert "not found" in json.loads(result.stderr)["error"]


def test_get_workspace_reflects_workspace_files(initialized_ree: Path) -> None:
    cmd = WriteFileCommand(args=WriteFileArgs(path="app.py", content="print('hi')\n"))
    assert runner.invoke(cli, ["execute", "--action", "-"], input=cmd.model_dump_json()).exit_code == 0

    result = runner.invoke(cli, ["get-workspace"])
    assert result.exit_code == 0
    workspace = json.loads(result.output)
    assert workspace["ree_id"] == "abc123"
    assert any(f.get("path") == "app.py" for f in workspace["files"])


def test_get_workspace_summary_omits_inline_file_content(initialized_ree: Path) -> None:
    cmd = WriteFileCommand(args=WriteFileArgs(path="app.py", content="print('hi')\n"))
    assert runner.invoke(cli, ["execute", "--action", "-"], input=cmd.model_dump_json()).exit_code == 0

    result = runner.invoke(cli, ["get-workspace", "--summary"])

    assert result.exit_code == 0
    workspace = json.loads(result.output)
    assert workspace["files"]
    # Typed entries always carry the key; summary mode never inlines the text.
    assert all(file["content"] is None for file in workspace["files"])
    assert all(file["content"] is None for file in workspace["ree_files"])


def test_build_archive_before_seal_writes_a_draft_bundle(initialized_ree: Path) -> None:
    result = runner.invoke(cli, ["build-archive"])

    assert result.exit_code == 0
    with zipfile.ZipFile(io.BytesIO(result.stdout_bytes)) as archive:
        manifest = json.loads(archive.read("ree/ree.json"))
    assert manifest["seal_hash"] is None
