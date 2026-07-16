"""The RunRegistry background-run state machine, exercised directly.

Real threads, real lock, real state transitions — only the runner body is
test-supplied (that is the registry's actual contract: it runs arbitrary
runners). Covers the paths the Docker-gated tiers never reach: runner
exceptions, cancellation racing completion, and log sequencing.
"""

from __future__ import annotations

import time
from threading import Event
from typing import Any

import pytest
from fastapi import HTTPException

from repo2ree_api.run_registry import RunRegistry

# ================================================
# Helpers
# ================================================


KNOWN_REE = "ree-1"

TERMINAL = frozenset({"succeeded", "failed", "canceled"})


def _registry() -> RunRegistry:
    def require_ree(ree_id: str) -> None:
        if ree_id != KNOWN_REE:
            raise HTTPException(status_code=404, detail="Workspace not found")

    return RunRegistry(require_ree)


def _wait_for(registry: RunRegistry, run_id: str, statuses: frozenset[str], timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = registry.get_run_state(KNOWN_REE, run_id)
        if state["status"] in statuses:
            return state
        time.sleep(0.01)
    pytest.fail(f"run {run_id} did not reach {sorted(statuses)} within {timeout}s")


# ================================================
# Start / success path
# ================================================


def test_start_background_rejects_unknown_ree():
    registry = _registry()
    with pytest.raises(HTTPException) as excinfo:
        registry.start_background("nope", "source", {}, "run", lambda e, r: ("succeeded", {}))
    assert excinfo.value.status_code == 404


def test_successful_run_reaches_succeeded_with_outputs():
    registry = _registry()
    run_state = registry.start_background(
        KNOWN_REE, "source", {"mode": "upload"}, "src", lambda e, r: ("succeeded", {"resolved": "abc"})
    )
    # run_state is live — the worker may already have finished by now, so the
    # queued → running transition is asserted in the blocking-runner lifecycle test
    assert run_state["runId"].startswith("src-")
    assert run_state["request"] == {"mode": "upload"}

    final = _wait_for(registry, run_state["runId"], TERMINAL)
    assert final["status"] == "succeeded"
    assert final["outputs"] == {"resolved": "abc"}
    assert final["finishedAt"] is not None
    # the internal sequence counter is stripped from the terminal state
    assert "_nextSeq" not in final


def test_run_summary_has_stable_keys():
    registry = _registry()
    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", lambda e, r: ("succeeded", {}))
    summary = registry.run_summary(run_state)
    assert list(summary) == ["runId", "reeId", "operation", "status", "createdAt", "startedAt", "finishedAt", "outputs"]
    _wait_for(registry, run_state["runId"], TERMINAL)


def test_idempotency_key_returns_original_run_without_duplicate_work():
    registry = _registry()
    release = Event()
    calls: list[str] = []

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        calls.append(run_id)
        release.wait(timeout=5.0)
        return "succeeded", {}

    first = registry.start_background(
        KNOWN_REE,
        "build",
        {"script": "ree-scripts/build_script.sh"},
        "build",
        _runner,
        idempotency_key="request-1",
    )
    second = registry.start_background(
        KNOWN_REE,
        "build",
        {"script": "ree-scripts/build_script.sh"},
        "build",
        _runner,
        idempotency_key="request-1",
    )

    assert second["runId"] == first["runId"]
    release.set()
    _wait_for(registry, first["runId"], TERMINAL)
    assert calls == [first["runId"]]


def test_idempotency_key_rejects_different_request_payload():
    registry = _registry()
    first = registry.start_background(
        KNOWN_REE,
        "evaluate",
        {"strict": False},
        "evaluate",
        lambda e, r: ("succeeded", {}),
        idempotency_key="request-1",
    )

    with pytest.raises(HTTPException) as excinfo:
        registry.start_background(
            KNOWN_REE,
            "evaluate",
            {"strict": True},
            "evaluate",
            lambda e, r: ("succeeded", {}),
            idempotency_key="request-1",
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail["code"] == "idempotency_conflict"
    assert excinfo.value.detail["details"]["runId"] == first["runId"]
    _wait_for(registry, first["runId"], TERMINAL)


# ================================================
# Status lifecycle
# ================================================


def test_run_starts_queued_then_running_with_started_at_stamped():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        return "succeeded", {}

    run_state = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    # Created queued with no start time; the worker stamps both when it begins.
    assert run_state["createdAt"] is not None

    running = _wait_for(registry, run_state["runId"], frozenset({"running"}))
    assert running["startedAt"] is not None
    assert running["startedAt"] >= running["createdAt"]
    assert running["finishedAt"] is None

    release.set()
    _wait_for(registry, run_state["runId"], TERMINAL)


def test_provision_run_reports_provisioning_while_working():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        return "succeeded", {}

    run_state = registry.start_background(KNOWN_REE, "provision", {}, "provision", _runner, require_ree_exists=False)
    _wait_for(registry, run_state["runId"], frozenset({"provisioning"}))
    release.set()
    assert _wait_for(registry, run_state["runId"], TERMINAL)["status"] == "succeeded"


# ================================================
# Failure paths
# ================================================


def test_runner_exception_finalizes_as_failed_with_error_log():
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        raise RuntimeError("docker cp exploded")

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    final = _wait_for(registry, run_state["runId"], TERMINAL)
    assert final["status"] == "failed"
    assert final["outputs"] == {}
    assert [(e["stream"], e["level"], e["message"]) for e in final["logs"]] == [
        ("system", "error", "docker cp exploded")
    ]


def test_runner_http_exception_finalizes_as_failed_with_detail_logged():
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        raise HTTPException(status_code=409, detail="seal in progress")

    run_state = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    final = _wait_for(registry, run_state["runId"], TERMINAL)
    assert final["status"] == "failed"
    assert final["logs"][0]["message"] == "seal in progress"


# ================================================
# Cancellation
# ================================================


def test_cancel_of_in_flight_run_transitions_canceling_then_canceled():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        # cooperative cancellation, the way the route runners check the flag
        if registry.is_cancel_requested(ree_id, run_id):
            return "canceled", {}
        return "succeeded", {}

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    run_id = run_state["runId"]
    _wait_for(registry, run_id, frozenset({"running"}))

    assert registry.mark_cancel_requested(KNOWN_REE, run_id) is True
    assert registry.get_run_state(KNOWN_REE, run_id)["status"] == "canceling"

    release.set()
    final = _wait_for(registry, run_id, TERMINAL)
    assert final["status"] == "canceled"
    assert final["finishedAt"] is not None


def test_cancel_after_runner_crash_still_reports_canceled():
    """A runner that dies after cancel was requested finalizes as canceled, not failed."""
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        raise RuntimeError("interrupted")

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    registry.mark_cancel_requested(KNOWN_REE, run_state["runId"])
    release.set()
    assert _wait_for(registry, run_state["runId"], TERMINAL)["status"] == "canceled"


def test_completed_run_is_not_retroactively_canceled():
    """finalize never demotes a result that already succeeded or failed."""
    registry = _registry()
    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", lambda e, r: ("succeeded", {}))
    run_id = run_state["runId"]
    _wait_for(registry, run_id, TERMINAL)

    assert registry.mark_cancel_requested(KNOWN_REE, run_id) is True
    assert registry.get_run_state(KNOWN_REE, run_id)["status"] == "succeeded"


def test_cancel_of_unknown_run_returns_false():
    registry = _registry()
    assert registry.mark_cancel_requested(KNOWN_REE, "no-such-run") is False
    assert registry.is_cancel_requested(KNOWN_REE, "no-such-run") is False


# ================================================
# Logs
# ================================================


def test_append_log_assigns_monotonic_sequence_numbers():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        return "succeeded", {}

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    run_id = run_state["runId"]
    registry.append_log(KNOWN_REE, run_id, "stdout", "info", "one")
    registry.append_log(KNOWN_REE, run_id, "stderr", "warn", "two")
    release.set()

    final = _wait_for(registry, run_id, TERMINAL)
    assert [(e["seq"], e["message"]) for e in final["logs"]] == [(1, "one"), (2, "two")]
    assert all(e["ts"] for e in final["logs"])


def test_append_log_to_unknown_run_is_a_noop():
    registry = _registry()
    registry.append_log(KNOWN_REE, "no-such-run", "stdout", "info", "lost")  # must not raise


def test_observe_returns_only_logs_after_sequence_cursor():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        return "succeeded", {}

    run = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    _wait_for(registry, run["runId"], frozenset({"running"}))
    registry.append_log(KNOWN_REE, run["runId"], "stdout", "info", "one")
    registry.append_log(KNOWN_REE, run["runId"], "stdout", "info", "two")

    summary, entries, cursor, changed = registry.observe(
        KNOWN_REE,
        run["runId"],
        after_seq=1,
        wait_seconds=0,
        limit=200,
    )

    assert summary["status"] == "running"
    assert [entry["message"] for entry in entries] == ["two"]
    assert cursor == "2"
    assert changed is True
    release.set()
    _wait_for(registry, run["runId"], TERMINAL)


def test_observe_timeout_returns_unchanged_active_run():
    registry = _registry()
    release = Event()
    run = registry.start_background(
        KNOWN_REE,
        "build",
        {},
        "build",
        lambda e, r: (release.wait(timeout=5.0) and "succeeded" or "failed", {}),
    )
    _wait_for(registry, run["runId"], frozenset({"running"}))

    summary, entries, cursor, changed = registry.observe(
        KNOWN_REE,
        run["runId"],
        after_seq=0,
        wait_seconds=0,
        limit=200,
    )

    assert summary["status"] == "running"
    assert entries == []
    assert cursor is None
    assert changed is False
    release.set()
    _wait_for(registry, run["runId"], TERMINAL)


def test_get_run_state_for_unknown_run_is_404():
    registry = _registry()
    with pytest.raises(HTTPException) as excinfo:
        registry.get_run_state(KNOWN_REE, "no-such-run")
    assert excinfo.value.status_code == 404
