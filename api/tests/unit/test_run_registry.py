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


KNOWN_ENTITY = "ree-1"

TERMINAL = frozenset({"succeeded", "failed", "canceled"})


def _registry(**kwargs: Any) -> RunRegistry:
    def require_entity(entity_id: str) -> None:
        if entity_id != KNOWN_ENTITY:
            raise HTTPException(status_code=404, detail="Workspace not found")

    return RunRegistry("reeId", require_entity, **kwargs)


def _wait_for(registry: RunRegistry, run_id: str, statuses: frozenset[str], timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = registry.get_run_state(KNOWN_ENTITY, run_id)
        if state["status"] in statuses:
            return state
        time.sleep(0.01)
    pytest.fail(f"run {run_id} did not reach {sorted(statuses)} within {timeout}s")


# ================================================
# Start / success path
# ================================================


def test_start_background_rejects_unknown_entity():
    registry = _registry()
    with pytest.raises(HTTPException) as excinfo:
        registry.start_background("nope", "source", {}, "run", lambda e, r: ("succeeded", {}))
    assert excinfo.value.status_code == 404


def test_successful_run_reaches_succeeded_with_outputs():
    registry = _registry()
    run_state = registry.start_background(
        KNOWN_ENTITY, "source", {"mode": "upload"}, "src", lambda e, r: ("succeeded", {"resolved": "abc"})
    )
    # run_state is live — the worker may already have finished by now, so the
    # initial "running" status is asserted in the blocking-runner cancel test
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
    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", lambda e, r: ("succeeded", {}))
    summary = registry.run_summary(run_state)
    assert list(summary) == ["runId", "reeId", "operation", "status", "createdAt", "startedAt", "finishedAt", "outputs"]
    _wait_for(registry, run_state["runId"], TERMINAL)


def test_run_summary_can_exclude_entity_id():
    registry = _registry(include_id_in_summary=False)
    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", lambda e, r: ("succeeded", {}))
    assert "reeId" not in registry.run_summary(run_state)
    _wait_for(registry, run_state["runId"], TERMINAL)


# ================================================
# Failure paths
# ================================================


def test_runner_exception_finalizes_as_failed_with_error_log():
    registry = _registry()

    def _runner(entity_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        raise RuntimeError("docker cp exploded")

    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", _runner)
    final = _wait_for(registry, run_state["runId"], TERMINAL)
    assert final["status"] == "failed"
    assert final["outputs"] == {}
    assert [(e["stream"], e["level"], e["message"]) for e in final["logs"]] == [
        ("system", "error", "docker cp exploded")
    ]


def test_runner_http_exception_finalizes_as_failed_with_detail_logged():
    registry = _registry()

    def _runner(entity_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        raise HTTPException(status_code=409, detail="seal in progress")

    run_state = registry.start_background(KNOWN_ENTITY, "build", {}, "build", _runner)
    final = _wait_for(registry, run_state["runId"], TERMINAL)
    assert final["status"] == "failed"
    assert final["logs"][0]["message"] == "seal in progress"


# ================================================
# Cancellation
# ================================================


def test_cancel_of_in_flight_run_transitions_canceling_then_canceled():
    registry = _registry()
    release = Event()

    def _runner(entity_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        # cooperative cancellation, the way the route runners check the flag
        if registry.is_cancel_requested(entity_id, run_id):
            return "canceled", {}
        return "succeeded", {}

    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", _runner)
    run_id = run_state["runId"]
    assert registry.get_run_state(KNOWN_ENTITY, run_id)["status"] == "running"

    assert registry.mark_cancel_requested(KNOWN_ENTITY, run_id) is True
    assert registry.get_run_state(KNOWN_ENTITY, run_id)["status"] == "canceling"

    release.set()
    final = _wait_for(registry, run_id, TERMINAL)
    assert final["status"] == "canceled"
    assert final["finishedAt"] is not None


def test_cancel_after_runner_crash_still_reports_canceled():
    """A runner that dies after cancel was requested finalizes as canceled, not failed."""
    registry = _registry()
    release = Event()

    def _runner(entity_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        raise RuntimeError("interrupted")

    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", _runner)
    registry.mark_cancel_requested(KNOWN_ENTITY, run_state["runId"])
    release.set()
    assert _wait_for(registry, run_state["runId"], TERMINAL)["status"] == "canceled"


def test_completed_run_is_not_retroactively_canceled():
    """finalize never demotes a result that already succeeded or failed."""
    registry = _registry()
    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", lambda e, r: ("succeeded", {}))
    run_id = run_state["runId"]
    _wait_for(registry, run_id, TERMINAL)

    assert registry.mark_cancel_requested(KNOWN_ENTITY, run_id) is True
    assert registry.get_run_state(KNOWN_ENTITY, run_id)["status"] == "succeeded"


def test_cancel_of_unknown_run_returns_false():
    registry = _registry()
    assert registry.mark_cancel_requested(KNOWN_ENTITY, "no-such-run") is False
    assert registry.is_cancel_requested(KNOWN_ENTITY, "no-such-run") is False


# ================================================
# Logs
# ================================================


def test_append_log_assigns_monotonic_sequence_numbers():
    registry = _registry()
    release = Event()

    def _runner(entity_id: str, run_id: str) -> tuple[str, dict[str, Any]]:
        release.wait(timeout=5.0)
        return "succeeded", {}

    run_state = registry.start_background(KNOWN_ENTITY, "source", {}, "src", _runner)
    run_id = run_state["runId"]
    registry.append_log(KNOWN_ENTITY, run_id, "stdout", "info", "one")
    registry.append_log(KNOWN_ENTITY, run_id, "stderr", "warn", "two")
    release.set()

    final = _wait_for(registry, run_id, TERMINAL)
    assert [(e["seq"], e["message"]) for e in final["logs"]] == [(1, "one"), (2, "two")]
    assert all(e["ts"] for e in final["logs"])


def test_append_log_to_unknown_run_is_a_noop():
    registry = _registry()
    registry.append_log(KNOWN_ENTITY, "no-such-run", "stdout", "info", "lost")  # must not raise


def test_get_run_state_for_unknown_run_is_404():
    registry = _registry()
    with pytest.raises(HTTPException) as excinfo:
        registry.get_run_state(KNOWN_ENTITY, "no-such-run")
    assert excinfo.value.status_code == 404
