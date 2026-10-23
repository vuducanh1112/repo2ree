"""The run store moves the author action a run carries: every status change it persists is journaled."""

from __future__ import annotations

import json
import subprocess
import sys
import typing
from pathlib import Path
from uuid import uuid4

import pytest

from repo2ree_api.storage import author_actions
from repo2ree_api.storage.json_run_store import JsonRunStore
from repo2ree_api.storage.run_store import StoredRun
from repo2ree_protocol.behaviour import close_journal, open_journal
from repo2ree_protocol.result import Failure


def _run(operation: str = "build", action: str | None = "build_runtime") -> StoredRun:
    return StoredRun.model_validate(
        {
            "run_id": "build-1",
            "ree_id": "ree-1",
            "operation": operation,
            "status": "queued",
            "created_at": "2026-01-01T00:00:00Z",
            "request": {},
            "action": action,
            # Fresh per run: the recorder holds the actions this process has open.
            "action_id": f"act-{uuid4().hex}" if action else None,
        }
    )


@pytest.fixture
def transitions(tmp_path: Path) -> typing.Iterator[typing.Callable[[], list[tuple[object, ...]]]]:
    opened = open_journal(tmp_path / "journal", "api")

    def read() -> list[tuple[object, ...]]:
        lines = [json.loads(line) for line in opened.path.read_text().splitlines()]
        return [(r["from"], r["to"], r["facts"]) for r in lines if r["kind"] == "transition"]

    yield read
    author_actions.settle_open("abandoned")
    close_journal()


def test_what_the_store_journals_keeps_the_published_contract(tmp_path: Path) -> None:
    opened = open_journal(tmp_path / "journal", "api", hosts=("supervisor",))
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run())
    store.begin("ree-1", "build-1")
    store.request_cancel("ree-1", "build-1")
    store.finalize("ree-1", "build-1", status="canceled", outputs={}, failure=None)
    close_journal(final=True)
    command = [sys.executable, "-m", "repo2ree_assurance_checker", "validate-journal", str(opened.path)]
    checked = subprocess.run(command, capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stdout


def test_each_persisted_status_change_moves_the_action_once(tmp_path: Path, transitions) -> None:
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run())
    store.begin("ree-1", "build-1")
    store.request_cancel("ree-1", "build-1")
    store.request_cancel("ree-1", "build-1")  # Already canceling: no change, no record.
    store.finalize("ree-1", "build-1", status="canceled", outputs={}, failure=None)

    named = {"action": "build_runtime", "run_id": "build-1"}
    assert transitions() == [
        (None, "requested", named),
        ("requested", "running", named),
        ("running", "canceling", named),
        ("canceling", "canceled", named),
    ]


def test_runs_interrupted_by_a_restart_fail_their_action(tmp_path: Path, transitions) -> None:
    JsonRunStore(tmp_path / "runs").create_idempotent(_run(operation="provision", action="create_ree"))
    restarted = JsonRunStore(tmp_path / "runs")
    restarted.begin("ree-1", "build-1")
    restarted.interrupt_incomplete()

    named = {"action": "create_ree", "run_id": "build-1"}
    assert transitions()[1:] == [
        ("requested", "running", named),
        ("running", "failed", named | {"failure_category": "internal"}),
    ]


def test_a_failure_records_its_category(tmp_path: Path, transitions) -> None:
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run())
    store.finalize(
        "ree-1",
        "build-1",
        status="failed",
        outputs={},
        failure=Failure(category="timeout", message="slow", origin="api"),
    )
    assert transitions()[-1][1:] == (
        "failed",
        {"action": "build_runtime", "run_id": "build-1", "failure_category": "timeout"},
    )


def test_a_settled_run_is_never_rewritten(tmp_path: Path, transitions) -> None:
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run())
    store.begin("ree-1", "build-1")
    store.interrupt_incomplete()
    stored = store.finalize("ree-1", "build-1", status="succeeded", outputs={}, failure=None)
    assert stored is not None
    assert stored.status == "failed"
    assert [step[1] for step in transitions()] == ["requested", "running", "failed"]


def test_a_run_no_author_asked_for_records_nothing(tmp_path: Path, transitions) -> None:
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run(action=None))
    store.begin("ree-1", "build-1")
    store.finalize("ree-1", "build-1", status="succeeded", outputs={}, failure=None)
    assert transitions() == []
