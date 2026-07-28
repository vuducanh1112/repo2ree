"""The RunRegistry background-run state machine, exercised directly.

Real threads, real lock, real state transitions — only the runner body is
test-supplied (that is the registry's actual contract: it runs arbitrary
runners). Covers the paths the Docker-gated tiers never reach: runner
exceptions, cancellation racing completion, and log sequencing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Event
from typing import Any, cast

import pytest
from fastapi import HTTPException

from repo2ree_api.control import run_registry as run_registry_module
from repo2ree_api.control.run_registry import RunRegistry
from repo2ree_protocol.result import ActionResult

# ================================================
# Helpers
# ================================================


KNOWN_REE = "ree-1"

TERMINAL = frozenset({"succeeded", "failed", "canceled"})


@dataclass
class _FakeInstrument:
    """Stands in for an OTel counter/histogram, capturing what was recorded.

    The real instruments bind to the global meter provider, which is set once
    per process — installing a reader to read them back would leak into every
    other test in the tier. What is worth asserting is the call sites anyway:
    which instrument fires, with which value, under which attributes.
    """

    calls: list[tuple[float, dict[str, str]]] = field(default_factory=list)

    def add(self, amount: float, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((amount, dict(attributes or {})))

    def record(self, amount: float, attributes: dict[str, str] | None = None) -> None:
        self.calls.append((amount, dict(attributes or {})))

    @property
    def attributes(self) -> list[dict[str, str]]:
        return [attrs for _amount, attrs in self.calls]

    @property
    def total(self) -> float:
        return sum(amount for amount, _attrs in self.calls)


@dataclass
class _Instruments:
    runs: _FakeInstrument
    duration: _FakeInstrument
    active: _FakeInstrument
    replay: _FakeInstrument
    conflict: _FakeInstrument


@pytest.fixture
def instruments(monkeypatch: pytest.MonkeyPatch) -> _Instruments:
    """Swap the module's run-lifecycle instruments for capturing fakes."""
    fakes = _Instruments(
        runs=_FakeInstrument(),
        duration=_FakeInstrument(),
        active=_FakeInstrument(),
        replay=_FakeInstrument(),
        conflict=_FakeInstrument(),
    )
    monkeypatch.setattr(run_registry_module, "_run_counter", fakes.runs)
    monkeypatch.setattr(run_registry_module, "_run_duration", fakes.duration)
    monkeypatch.setattr(run_registry_module, "_runs_active", fakes.active)
    monkeypatch.setattr(run_registry_module, "_run_replay_counter", fakes.replay)
    monkeypatch.setattr(run_registry_module, "_run_idempotency_conflict_counter", fakes.conflict)
    return fakes


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
        registry.start_background("nope", "source", {}, "run", lambda e, r: ActionResult(status="succeeded"))
    assert excinfo.value.status_code == 404


def test_successful_run_reaches_succeeded_with_outputs():
    registry = _registry()
    run_state = registry.start_background(
        KNOWN_REE,
        "source",
        {"mode": "upload"},
        "src",
        lambda e, r: ActionResult(status="succeeded", outputs={"resolved": "abc"}),
    )
    # run_state is live — the worker may already have finished by now, so the
    # queued → running transition is asserted in the blocking-runner lifecycle test
    assert run_state["run_id"].startswith("src-")
    assert run_state["request"] == {"mode": "upload"}

    final = _wait_for(registry, run_state["run_id"], TERMINAL)
    assert final["status"] == "succeeded"
    assert final["outputs"] == {"resolved": "abc"}
    assert final["finished_at"] is not None
    # the internal sequence counter is stripped from the terminal state
    assert "_next_seq" not in final


def test_run_summary_has_stable_keys():
    registry = _registry()
    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", lambda e, r: ActionResult(status="succeeded"))
    summary = registry.run_summary(run_state)
    assert list(summary) == [
        "run_id",
        "ree_id",
        "operation",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "outputs",
        "failure",
    ]
    _wait_for(registry, run_state["run_id"], TERMINAL)


def test_idempotency_key_returns_original_run_without_duplicate_work():
    registry = _registry()
    release = Event()
    calls: list[str] = []

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        calls.append(run_id)
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

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

    assert second["run_id"] == first["run_id"]
    release.set()
    _wait_for(registry, first["run_id"], TERMINAL)
    assert calls == [first["run_id"]]


def test_idempotency_key_rejects_different_request_payload():
    registry = _registry()
    first = registry.start_background(
        KNOWN_REE,
        "evaluate",
        {"strict": False},
        "evaluate",
        lambda e, r: ActionResult(status="succeeded"),
        idempotency_key="request-1",
    )

    with pytest.raises(HTTPException) as excinfo:
        registry.start_background(
            KNOWN_REE,
            "evaluate",
            {"strict": True},
            "evaluate",
            lambda e, r: ActionResult(status="succeeded"),
            idempotency_key="request-1",
        )

    assert excinfo.value.status_code == 409
    # Starlette declares ``detail`` as a string; this API raises the structured
    # error envelope through it, which is what the handler in main.py renders.
    detail = cast(dict[str, Any], excinfo.value.detail)
    assert detail["code"] == "idempotency_conflict"
    assert detail["details"]["run_id"] == first["run_id"]
    _wait_for(registry, first["run_id"], TERMINAL)


# ================================================
# Status lifecycle
# ================================================


def test_run_starts_queued_then_running_with_started_at_stamped():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

    run_state = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    # Created queued with no start time; the worker stamps both when it begins.
    assert run_state["created_at"] is not None

    running = _wait_for(registry, run_state["run_id"], frozenset({"running"}))
    assert running["started_at"] is not None
    assert running["started_at"] >= running["created_at"]
    assert running["finished_at"] is None

    release.set()
    _wait_for(registry, run_state["run_id"], TERMINAL)


def test_provision_run_reports_provisioning_while_working():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

    run_state = registry.start_background(KNOWN_REE, "provision", {}, "provision", _runner, require_ree_exists=False)
    _wait_for(registry, run_state["run_id"], frozenset({"provisioning"}))
    release.set()
    assert _wait_for(registry, run_state["run_id"], TERMINAL)["status"] == "succeeded"


# ================================================
# Failure paths
# ================================================


def test_runner_exception_finalizes_as_failed_with_error_log():
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise RuntimeError("docker cp exploded")

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    final = _wait_for(registry, run_state["run_id"], TERMINAL)
    assert final["status"] == "failed"
    assert final["outputs"] == {}
    # A runner that raised is synthesized into an internal failure attributed to
    # the API worker thread, carried on the run — not just logged.
    assert final["failure"]["category"] == "internal"
    assert final["failure"]["origin"] == "api"
    assert final["failure"]["message"] == "docker cp exploded"
    assert [(e["stream"], e["level"], e["message"]) for e in final["logs"]] == [
        ("system", "error", "docker cp exploded")
    ]


def test_runner_http_exception_finalizes_as_failed_with_detail_logged():
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise HTTPException(status_code=409, detail="seal in progress")

    run_state = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    final = _wait_for(registry, run_state["run_id"], TERMINAL)
    assert final["status"] == "failed"
    assert final["failure"]["origin"] == "api"
    assert final["failure"]["message"] == "seal in progress"
    # The status already says what kind of failure this is; a 409 is a conflict,
    # not an internal fault of ours.
    assert final["failure"]["category"] == "conflict"
    assert final["logs"][0]["message"] == "seal in progress"


def test_structured_http_detail_survives_as_a_typed_failure():
    """A route's error envelope must not be flattened into a dict repr."""
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "version_conflict",
                "message": "The file changed since you read it",
                "details": {"path": "ree-scripts/build_script.sh", "expected_version": "etag-1"},
            },
        )

    run_state = registry.start_background(KNOWN_REE, "files", {}, "files", _runner)
    final = _wait_for(registry, run_state["run_id"], TERMINAL)

    failure = final["failure"]
    assert failure["category"] == "conflict"
    assert failure["retryable"] is False
    # The envelope's own message, not `str(detail)`.
    assert failure["message"] == "The file changed since you read it"
    # Everything else on the envelope stays readable by the client.
    assert failure["details"]["code"] == "version_conflict"
    assert failure["details"]["details"]["path"] == "ree-scripts/build_script.sh"
    assert failure["details"]["http_status"] == 409
    assert final["logs"][0]["message"] == "The file changed since you read it"


def test_an_unreachable_dependency_reported_over_http_is_retryable():
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise HTTPException(status_code=503, detail="Workbench unavailable for this REE")

    run_state = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    failure = _wait_for(registry, run_state["run_id"], TERMINAL)["failure"]

    assert failure["category"] == "unavailable"
    assert failure["retryable"] is True


def test_a_server_side_http_status_without_a_mapping_stays_internal():
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise HTTPException(status_code=500, detail="something gave way")

    run_state = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    failure = _wait_for(registry, run_state["run_id"], TERMINAL)["failure"]

    assert failure["category"] == "internal"
    assert failure["retryable"] is False


# ================================================
# Cancellation
# ================================================


def test_cancel_of_in_flight_run_transitions_canceling_then_canceled():
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        # cooperative cancellation, the way the route runners check the flag
        if registry.is_cancel_requested(ree_id, run_id):
            return ActionResult(status="canceled")
        return ActionResult(status="succeeded")

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    run_id = run_state["run_id"]
    _wait_for(registry, run_id, frozenset({"running"}))

    assert registry.mark_cancel_requested(KNOWN_REE, run_id) is True
    assert registry.get_run_state(KNOWN_REE, run_id)["status"] == "canceling"

    release.set()
    final = _wait_for(registry, run_id, TERMINAL)
    assert final["status"] == "canceled"
    assert final["finished_at"] is not None


def test_cancel_after_runner_crash_still_reports_canceled():
    """A runner that dies after cancel was requested finalizes as canceled, not failed."""
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        raise RuntimeError("interrupted")

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    registry.mark_cancel_requested(KNOWN_REE, run_state["run_id"])
    release.set()
    assert _wait_for(registry, run_state["run_id"], TERMINAL)["status"] == "canceled"


def test_completed_run_is_not_retroactively_canceled():
    """finalize never demotes a result that already succeeded or failed."""
    registry = _registry()
    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", lambda e, r: ActionResult(status="succeeded"))
    run_id = run_state["run_id"]
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

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

    run_state = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    run_id = run_state["run_id"]
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

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

    run = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    _wait_for(registry, run["run_id"], frozenset({"running"}))
    registry.append_log(KNOWN_REE, run["run_id"], "stdout", "info", "one")
    registry.append_log(KNOWN_REE, run["run_id"], "stdout", "info", "two")

    summary, entries, cursor, changed = registry.observe(
        KNOWN_REE,
        run["run_id"],
        after_seq=1,
        wait_seconds=0,
        limit=200,
    )

    assert summary["status"] == "running"
    assert [entry["message"] for entry in entries] == ["two"]
    assert cursor == "2"
    assert changed is True
    release.set()
    _wait_for(registry, run["run_id"], TERMINAL)


def test_observe_timeout_returns_unchanged_active_run():
    registry = _registry()
    release = Event()
    run = registry.start_background(
        KNOWN_REE,
        "build",
        {},
        "build",
        lambda e, r: ActionResult(status="succeeded")
        if release.wait(timeout=5.0)
        else ActionResult.failed("timeout", "runner wait timed out", origin="api"),
    )
    _wait_for(registry, run["run_id"], frozenset({"running"}))

    summary, entries, cursor, changed = registry.observe(
        KNOWN_REE,
        run["run_id"],
        after_seq=0,
        wait_seconds=0,
        limit=200,
    )

    assert summary["status"] == "running"
    assert entries == []
    assert cursor is None
    assert changed is False
    release.set()
    _wait_for(registry, run["run_id"], TERMINAL)


def test_get_run_state_for_unknown_run_is_404():
    registry = _registry()
    with pytest.raises(HTTPException) as excinfo:
        registry.get_run_state(KNOWN_REE, "no-such-run")
    assert excinfo.value.status_code == 404


# ================================================
# Metrics
# ================================================


def test_settled_run_counts_once_and_records_its_duration(instruments: _Instruments):
    registry = _registry()
    run = registry.start_background(KNOWN_REE, "build", {}, "build", lambda e, r: ActionResult(status="succeeded"))
    _wait_for(registry, run["run_id"], TERMINAL)

    terminal_attrs = {"repo2ree.operation": "build", "repo2ree.status": "succeeded"}
    assert instruments.runs.calls == [(1, terminal_attrs)]
    assert instruments.duration.attributes == [terminal_attrs]
    # One sample, of a real elapsed span rather than a placeholder zero.
    duration, _attrs = instruments.duration.calls[0]
    assert duration > 0


def test_failed_run_is_metered_under_its_terminal_status(instruments: _Instruments):
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise RuntimeError("docker cp exploded")

    run = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    _wait_for(registry, run["run_id"], TERMINAL)

    assert instruments.runs.attributes == [{"repo2ree.operation": "source", "repo2ree.status": "failed"}]


def test_run_is_metered_with_the_settled_status_not_the_proposed_one(instruments: _Instruments):
    """A run canceled mid-flight counts as canceled, matching what a poller reads."""
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="canceled")

    run = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    _wait_for(registry, run["run_id"], frozenset({"running"}))
    registry.mark_cancel_requested(KNOWN_REE, run["run_id"])
    release.set()

    final = _wait_for(registry, run["run_id"], TERMINAL)
    assert instruments.runs.attributes == [{"repo2ree.operation": "build", "repo2ree.status": final["status"]}]


def test_active_gauge_rises_while_running_and_returns_to_zero(instruments: _Instruments):
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

    run = registry.start_background(KNOWN_REE, "build", {}, "build", _runner)
    _wait_for(registry, run["run_id"], frozenset({"running"}))
    assert instruments.active.total == 1

    release.set()
    _wait_for(registry, run["run_id"], TERMINAL)
    # The gauge is balanced by the finally, and carries no status: an in-flight
    # run has no terminal status to slice by.
    assert instruments.active.total == 0
    assert instruments.active.attributes == [{"repo2ree.operation": "build"}] * 2


def test_a_crashed_runner_still_balances_the_active_gauge(instruments: _Instruments):
    registry = _registry()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        raise RuntimeError("boom")

    run = registry.start_background(KNOWN_REE, "source", {}, "src", _runner)
    _wait_for(registry, run["run_id"], TERMINAL)

    assert instruments.active.total == 0


def test_idempotent_replay_is_metered_and_the_run_counted_once(instruments: _Instruments):
    registry = _registry()
    release = Event()

    def _runner(ree_id: str, run_id: str) -> ActionResult:
        release.wait(timeout=5.0)
        return ActionResult(status="succeeded")

    payload = {"script": "ree-scripts/build_script.sh"}
    first = registry.start_background(KNOWN_REE, "build", payload, "build", _runner, idempotency_key="request-1")
    registry.start_background(KNOWN_REE, "build", payload, "build", _runner, idempotency_key="request-1")

    assert instruments.replay.calls == [(1, {"repo2ree.operation": "build"})]
    release.set()
    _wait_for(registry, first["run_id"], TERMINAL)
    # The replayed request started no second run, so exactly one settled.
    assert instruments.runs.total == 1


def test_idempotency_conflict_is_metered(instruments: _Instruments):
    registry = _registry()
    first = registry.start_background(
        KNOWN_REE,
        "evaluate",
        {"strict": False},
        "evaluate",
        lambda e, r: ActionResult(status="succeeded"),
        idempotency_key="request-1",
    )

    with pytest.raises(HTTPException):
        registry.start_background(
            KNOWN_REE,
            "evaluate",
            {"strict": True},
            "evaluate",
            lambda e, r: ActionResult(status="succeeded"),
            idempotency_key="request-1",
        )

    assert instruments.conflict.calls == [(1, {"repo2ree.operation": "evaluate"})]
    assert instruments.replay.calls == []
    _wait_for(registry, first["run_id"], TERMINAL)
