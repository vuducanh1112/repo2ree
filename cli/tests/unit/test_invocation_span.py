"""Every ``ree`` invocation is one span, named after its command, under the caller's trace, ending as it ended.

Run as a process of its own, as callers run it: telemetry is set up once per process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from repo2ree_cli.cli import REFUSED
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

TRACE_ID = "a" * 32
PARENT_SPAN_ID = "b" * 16


def ree(trace_file: Path, *words: str, input: str | None = None) -> subprocess.CompletedProcess[str]:  # noqa: A002
    environment = {
        key: value for key, value in os.environ.items() if key not in {"TRACE_RELAY", "OTLP_ENDPOINT", "TRACEPARENT"}
    }
    environment["TRACE_FILE"] = str(trace_file)
    environment["TRACEPARENT"] = f"00-{TRACE_ID}-{PARENT_SPAN_ID}-01"
    return subprocess.run(
        [sys.executable, "-m", "repo2ree_cli", *words],
        env=environment,
        input=input,
        capture_output=True,
        text=True,
        check=False,
    )


def spans(trace_file: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in trace_file.read_text().splitlines()]


def named(trace_file: Path, name: str) -> dict[str, Any]:
    return next(span for span in spans(trace_file) if span["name"] == name)


@pytest.fixture
def trace_file(tmp_path: Path) -> Path:
    return tmp_path / "traces.ndjson"


@pytest.fixture
def root(tmp_path: Path, trace_file: Path) -> Path:
    root = tmp_path / "ree"
    assert ree(trace_file, "-C", str(root), "initialize-ree", "--name", "demo").returncode == 0
    trace_file.unlink()
    return root


def test_a_read_is_one_span_under_the_callers_trace(root: Path, trace_file: Path) -> None:
    completed = ree(trace_file, "-C", str(root), "--json", "status")

    assert completed.returncode == 0, completed.stderr
    [span] = spans(trace_file)
    assert span["name"] == "ree status"
    assert span["context"]["trace_id"] == f"0x{TRACE_ID}"
    assert span["parent_id"] == f"0x{PARENT_SPAN_ID}"
    assert span["attributes"]["repo2ree.cli.command"] == "status"
    assert span["attributes"]["repo2ree.status"] == "succeeded"
    assert span["attributes"]["repo2ree.exit_code"] == 0
    assert span["status"]["status_code"] == "UNSET"


def test_a_run_nests_its_session_under_the_invocation(root: Path, trace_file: Path) -> None:
    completed = ree(
        trace_file, "-C", str(root), "--json", "write-script", RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, input="x"
    )

    assert completed.returncode == 0, completed.stderr
    invocation = named(trace_file, "ree write-script")
    session = named(trace_file, "session.write_script")
    assert session["parent_id"] == invocation["context"]["span_id"]
    assert invocation["attributes"]["repo2ree.status"] == "succeeded"


def test_a_nested_command_is_named_by_all_its_words(root: Path, trace_file: Path) -> None:
    ree(trace_file, "-C", str(root), "--json", "review", "activate-experiment-environment", "--review-id", "missing")

    assert named(trace_file, "ree review activate-experiment-environment")["attributes"]["repo2ree.cli.command"] == (
        "review activate-experiment-environment"
    )


def test_a_refusal_ends_the_span_as_an_error_with_its_reason(tmp_path: Path, trace_file: Path) -> None:
    completed = ree(trace_file, "-C", str(tmp_path / "nowhere"), "--json", "status")

    assert completed.returncode == REFUSED
    [span] = spans(trace_file)
    assert span["name"] == "ree status"
    assert span["attributes"]["repo2ree.failure.category"] == "precondition"
    assert span["attributes"]["repo2ree.exit_code"] == REFUSED
    assert span["status"]["status_code"] == "ERROR"


def test_a_command_line_that_names_no_command_is_still_traced(trace_file: Path) -> None:
    completed = ree(trace_file, "no-such-command")

    assert completed.returncode == REFUSED
    [span] = spans(trace_file)
    assert span["name"] == "ree"
    assert span["attributes"]["repo2ree.exit_code"] == REFUSED


def test_without_a_destination_nothing_is_recorded(root: Path, trace_file: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if key not in {"TRACE_RELAY", "OTLP_ENDPOINT"}}
    environment.pop("TRACE_FILE", None)
    completed = subprocess.run(
        [sys.executable, "-m", "repo2ree_cli", "-C", str(root), "--json", "status"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["status"] == "succeeded"
    assert not trace_file.exists()
