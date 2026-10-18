"""The run store is the Run machine's owner: every status change it persists is journaled."""

from __future__ import annotations

import json
import typing
from pathlib import Path

import pytest

from repo2ree_api.contracts import RunStatus
from repo2ree_api.storage.json_run_store import JsonRunStore
from repo2ree_api.storage.run_store import StoredRun
from repo2ree_protocol.behaviour import MACHINES, close_journal, open_journal
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import Failure


def _run(run_id: str = "build-1", operation: str = "build") -> StoredRun:
    return StoredRun.model_validate(
        {
            "run_id": run_id,
            "ree_id": "ree-1",
            "operation": operation,
            "status": "queued",
            "created_at": "2026-01-01T00:00:00Z",
            "request": {},
        }
    )


@pytest.fixture
def transitions(tmp_path: Path) -> typing.Iterator[typing.Callable[[], list[tuple[object, ...]]]]:
    opened = open_journal(tmp_path / "journal", "api")

    def read() -> list[tuple[object, ...]]:
        lines = [json.loads(line) for line in opened.path.read_text().splitlines()]
        return [(r["key"], r["from"], r["to"], r["facts"]) for r in lines if r["kind"] == "transition"]

    yield read
    close_journal()


def test_run_statuses_are_the_specified_machine() -> None:
    assert set(typing.get_args(RunStatus)) == set(MACHINES["Run"].states)


def test_each_persisted_status_change_is_one_transition(tmp_path: Path, transitions) -> None:
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run())
    store.begin("ree-1", "build-1")
    store.request_cancel("ree-1", "build-1")
    store.request_cancel("ree-1", "build-1")  # Already canceling: no change, no record.
    context = ExecutionContext.new(ree_id="ree-1")
    store.finalize("ree-1", "build-1", status="canceled", outputs={}, failure=None, context=context)

    assert transitions() == [
        ("build-1", None, "queued", {"operation": "build"}),
        ("build-1", "queued", "running", {}),
        ("build-1", "running", "canceling", {}),
        ("build-1", "canceling", "canceled", {"attempt_id": context.attempt_id, "failure_category": None}),
    ]


def test_runs_interrupted_by_a_restart_are_journaled_as_failed(tmp_path: Path, transitions) -> None:
    JsonRunStore(tmp_path / "runs").create_idempotent(_run(operation="provision"))
    restarted = JsonRunStore(tmp_path / "runs")
    restarted.begin("ree-1", "build-1")
    restarted.interrupt_incomplete()

    assert transitions()[1:] == [
        ("build-1", "queued", "provisioning", {}),
        ("build-1", "provisioning", "failed", {"attempt_id": None, "failure_category": "internal"}),
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
    assert transitions()[-1] == ("build-1", "queued", "failed", {"attempt_id": None, "failure_category": "timeout"})


def test_a_settled_run_is_never_rewritten(tmp_path: Path, transitions) -> None:
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(_run())
    store.begin("ree-1", "build-1")
    store.interrupt_incomplete()
    stored = store.finalize("ree-1", "build-1", status="succeeded", outputs={}, failure=None)
    assert stored is not None
    assert stored.status == "failed"
    assert [step[2] for step in transitions()] == ["queued", "running", "failed"]
