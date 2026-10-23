"""The API records each author action on one REE: requested, then the answer the author is given."""

from __future__ import annotations

import json
import subprocess
import sys
import typing
from pathlib import Path

import pytest
from fastapi import HTTPException

from repo2ree_api.storage import author_actions
from repo2ree_api.storage.json_run_store import JsonRunStore
from repo2ree_api.storage.run_store import StoredRun
from repo2ree_protocol.behaviour import close_journal, open_journal
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, HistoryReference

Records = typing.Callable[[], list[tuple[object, ...]]]


@pytest.fixture
def actions(tmp_path: Path) -> typing.Iterator[Records]:
    opened = open_journal(tmp_path / "journal", "api")

    def read() -> list[tuple[object, ...]]:
        lines = [json.loads(line) for line in opened.path.read_text().splitlines()]
        return [
            (r["key"], r["from"], r["to"], r["facts"])
            for r in lines
            if r["kind"] == "transition" and r["subject"] == "AuthorApiAction"
        ]

    yield read
    author_actions.settle_open("abandoned")
    close_journal()


def _recorded(context: ExecutionContext) -> ActionResult:
    history = HistoryReference(
        selection_version=1,
        attempt_id=context.attempt_id,
        scope=".",
        capture_status="captured",
        operation_status="succeeded",
    )
    return ActionResult(status="succeeded", context=context, history=history)


def test_a_synchronous_action_is_requested_then_answered_with_its_attempt(actions: Records) -> None:
    context = ExecutionContext.new(ree_id="ree-1")
    with author_actions.author_api_action("write_file", "ree-1", path="overlay/run.sh") as action_id:
        author_actions.learn_attempt(_recorded(context))

    assert actions() == [
        (action_id, None, "requested", {"action": "write_file", "path": "overlay/run.sh"}),
        (action_id, "requested", "succeeded", {"action": "write_file", "attempt_id": context.attempt_id}),
    ]


def test_an_attempt_the_workbench_did_not_record_is_not_named(actions: Records) -> None:
    unrecorded = ActionResult.failed("unavailable", "bench gone", origin="supervisor")

    def lint() -> None:
        with author_actions.author_api_action("lint_scripts", "ree-1"):
            author_actions.learn_attempt(unrecorded.model_copy(update={"context": ExecutionContext.new()}))
            raise HTTPException(status_code=503, detail="bench gone")

    with pytest.raises(HTTPException):
        lint()

    assert actions()[-1][1:] == ("requested", "failed", {"action": "lint_scripts", "http_status": 503})


def test_a_run_moves_its_action_along_and_names_the_attempt_it_recorded(tmp_path: Path, actions: Records) -> None:
    store = JsonRunStore(tmp_path / "runs")
    run = StoredRun.model_validate(
        {
            "run_id": "build-1",
            "ree_id": "ree-1",
            "operation": "build",
            "status": "queued",
            "created_at": "2026-01-01T00:00:00Z",
            "request": {},
            "action": "build_runtime",
            "action_id": "act-1",
        }
    )
    store.create_idempotent(run)
    store.begin("ree-1", "build-1")
    context = ExecutionContext.new(ree_id="ree-1")
    recorded = _recorded(context)
    store.finalize(
        "ree-1", "build-1", status="succeeded", outputs={}, failure=None, context=context, history=recorded.history
    )

    named = {"action": "build_runtime", "run_id": "build-1"}
    assert actions() == [
        ("act-1", None, "requested", named),
        ("act-1", "requested", "running", named),
        ("act-1", "running", "succeeded", named | {"attempt_id": context.attempt_id}),
    ]


def test_an_upload_continues_the_action_its_slot_opened(tmp_path: Path, actions: Records) -> None:
    action_id = author_actions.start("upload_source", "ree-1")
    store = JsonRunStore(tmp_path / "runs")
    store.create_idempotent(
        StoredRun.model_validate(
            {
                "run_id": "source-1",
                "ree_id": "ree-1",
                "operation": "source",
                "status": "queued",
                "created_at": "2026-01-01T00:00:00Z",
                "request": {},
                "action": "upload_source",
                "action_id": action_id,
            }
        )
    )
    store.begin("ree-1", "source-1")

    assert [(record[1], record[2]) for record in actions()] == [(None, "requested"), ("requested", "running")]


def test_actions_still_open_fail_before_the_journal_closes(tmp_path: Path) -> None:
    opened = open_journal(tmp_path / "journal", "api", hosts=("supervisor",))
    abandoned = author_actions.start("upload_source", "ree-1")
    author_actions.settle_open("abandoned")
    close_journal(final=True)

    records = [json.loads(line) for line in opened.path.read_text().splitlines()]
    last = next(r for r in reversed(records) if r.get("subject") == "AuthorApiAction")
    assert (last["key"], last["to"], last["facts"]["failure_category"]) == (abandoned, "failed", "abandoned")
    command = [sys.executable, "-m", "repo2ree_assurance_checker", "validate-journal", str(opened.path)]
    checked = subprocess.run(command, capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stdout
