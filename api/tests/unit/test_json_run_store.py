"""Filesystem behavior of the temporary JSON background-run backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_api.storage.json_run_store import JsonRunStore
from repo2ree_api.storage.run_store import IdempotencyConflictError, StoredRun
from repo2ree_protocol.result import Failure


def _run(
    *,
    run_id: str = "build-1",
    status: str = "queued",
    idempotency_key: str | None = None,
    fingerprint: str | None = None,
) -> StoredRun:
    return StoredRun.model_validate(
        {
            "run_id": run_id,
            "ree_id": "ree-1",
            "operation": "build",
            "status": status,
            "created_at": "2026-01-01T00:00:00Z",
            "request": {"script": "build.sh"},
            "idempotency_key": idempotency_key,
            "request_fingerprint": fingerprint,
        }
    )


def test_state_logs_and_idempotency_survive_reloading(tmp_path: Path):
    store = JsonRunStore(tmp_path)
    stored, created = store.create_idempotent(_run(idempotency_key="request-1", fingerprint="same"))
    assert created is True
    store.begin(stored.ree_id, stored.run_id)
    store.append_log(stored.ree_id, stored.run_id, stream="stdout", level="info", message="one")
    store.finalize(
        stored.ree_id,
        stored.run_id,
        status="succeeded",
        outputs={"artifact": "runtime.tar"},
        failure=None,
    )

    reloaded = JsonRunStore(tmp_path)
    state = reloaded.get(stored.ree_id, stored.run_id)
    assert state is not None
    assert state.status == "succeeded"
    assert state.outputs == {"artifact": "runtime.tar"}
    assert [entry.message for entry in reloaded.list_logs("ree-1", "build-1", after_seq=0)] == ["one"]

    replay, replay_created = reloaded.create_idempotent(
        _run(run_id="build-2", idempotency_key="request-1", fingerprint="same")
    )
    assert replay_created is False
    assert replay.run_id == "build-1"


def test_reloaded_idempotency_key_rejects_another_payload(tmp_path: Path):
    store = JsonRunStore(tmp_path)
    store.create_idempotent(_run(idempotency_key="request-1", fingerprint="first"))

    with pytest.raises(IdempotencyConflictError) as excinfo:
        JsonRunStore(tmp_path).create_idempotent(
            _run(run_id="build-2", idempotency_key="request-1", fingerprint="second")
        )

    assert excinfo.value.existing.run_id == "build-1"


def test_partial_final_log_line_is_ignored_and_sequence_recovers(tmp_path: Path):
    store = JsonRunStore(tmp_path)
    store.create_idempotent(_run())
    store.append_log("ree-1", "build-1", stream="stdout", level="info", message="complete")
    with (tmp_path / "build-1" / "logs.jsonl").open("a", encoding="utf-8") as output:
        output.write('{"seq":2,"message":"partial"')

    reloaded = JsonRunStore(tmp_path)
    assert [entry.seq for entry in reloaded.list_logs("ree-1", "build-1", after_seq=0)] == [1]
    appended = reloaded.append_log("ree-1", "build-1", stream="stderr", level="warn", message="recovered")
    assert appended is not None
    assert appended.seq == 2
    assert [entry.seq for entry in JsonRunStore(tmp_path).list_logs("ree-1", "build-1", after_seq=0)] == [1, 2]


def test_startup_recovery_atomically_fails_incomplete_runs(tmp_path: Path):
    store = JsonRunStore(tmp_path)
    store.create_idempotent(_run(status="running"))

    interrupted = store.interrupt_incomplete()

    assert [run.run_id for run in interrupted] == ["build-1"]
    recovered = JsonRunStore(tmp_path).get("ree-1", "build-1")
    assert recovered is not None
    assert recovered.status == "failed"
    assert recovered.finished_at is not None
    assert recovered.failure == Failure(
        category="internal",
        message="API process stopped before the run completed",
        retryable=True,
        origin="api",
        details={"code": "run_interrupted"},
    )


def test_cancel_request_survives_reloading(tmp_path: Path):
    store = JsonRunStore(tmp_path)
    store.create_idempotent(_run(status="running"))

    requested = store.request_cancel("ree-1", "build-1")
    assert requested is not None
    assert requested.status == "canceling"
    assert requested.cancel_requested_at is not None

    reloaded = JsonRunStore(tmp_path)
    assert reloaded.is_cancel_requested("ree-1", "build-1") is True
    persisted = reloaded.get("ree-1", "build-1")
    assert persisted is not None
    assert persisted.status == "canceling"


def test_invalid_state_document_fails_loading(tmp_path: Path):
    state = tmp_path / "bad-run" / "state.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"run_id": "bad-run"}', encoding="utf-8")

    with pytest.raises(ValueError):
        JsonRunStore(tmp_path)
