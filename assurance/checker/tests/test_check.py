from __future__ import annotations

import tomllib
from itertools import pairwise
from typing import Any

import pytest

from repo2ree_assurance_checker.check import check, judge_occurrences, replay
from repo2ree_assurance_checker.evidence import Event, Evidence, Source
from repo2ree_assurance_checker.files import load_spec
from repo2ree_assurance_checker.spec import Invariant, Spec

EXAMPLE_RULES = tomllib.loads(
    """
# A requirement on a message: the citation that orders the journal against Git.
[[invariant]]
id = "example-execution-was-dispatched"
pattern = "requires"
summary = "Every attempt that executed was started by the supervisor."
when = { entity = "Attempt", to = "executing" }
require = { boundary = "start_run", message = "start_run", key_from = "$key", order = "before" }

# A guard on a fact's listed values, entered from the absent state.
[[invariant]]
id = "example-source-receipts-come-from-acquisition"
pattern = "guard"
summary = "Source evidence appears only by acquiring source or loading a bundle."
require = { where = { operation = { in = ["acquire_source", "load_ree_bundle"] } } }
[invariant.when]
entity = "Receipt"
from = ["(none)", "missing", "not_applicable"]
to = ["current", "stale"]
where = { kind = "acquire_source" }
"""
)["invariant"]


def with_examples(spec: Spec) -> Spec:
    return spec.model_copy(
        update={"invariants": (*spec.invariants, *(Invariant.model_validate(rule) for rule in EXAMPLE_RULES))}
    )


SPEC = with_examples(load_spec())
REE = "ree-1"


def journal(source_id: str = "api-000001", *, closed: bool = True, complete: bool = True) -> Source:
    return Source(
        id=source_id,
        kind="journal",
        process="api",
        rank=int(source_id.rsplit("-", 1)[1]),
        hosts=frozenset({"api", "supervisor"}),
        complete=complete,
        closed=closed,
        vocabulary=SPEC.vocabulary_digest,
    )


def bench(source_id: str = "workbench-000001", *, closed: bool = True, complete: bool = True) -> Source:
    return Source(
        id=source_id,
        kind="journal",
        process="workbench",
        instance="lab-1",
        rank=int(source_id.rsplit("-", 1)[1]),
        hosts=frozenset({"workbench"}),
        complete=complete,
        closed=closed,
        vocabulary=SPEC.vocabulary_digest,
    )


def environment(source_id: str = "environment-000001") -> Source:
    return Source(
        id=source_id,
        kind="journal",
        process="environment",
        rank=int(source_id.rsplit("-", 1)[1]),
        hosts=frozenset({"environment"}),
        complete=True,
        closed=True,
        vocabulary=SPEC.vocabulary_digest,
    )


def git(*partitions: str, complete: bool = True, cut: dict[str, tuple[int, int]] | None = None) -> Source:
    return Source(
        id="git:ree",
        kind="git",
        process="core",
        rank=0,
        hosts=frozenset({"core"}),
        complete=complete,
        closed=False,
        partitions=frozenset(partitions),
        cut=cut,
    )


def stores(cut: dict[str, tuple[int, int]] | None = None) -> Source:
    return Source(
        id="stores",
        kind="store",
        process="stores",
        rank=0,
        hosts=frozenset({"api", "supervisor"}),
        complete=True,
        closed=True,
        cut=cut,
    )


class Recorder:
    def __init__(self) -> None:
        self.events: list[Event] = []
        self.positions: dict[str, int] = {}

    def _add(self, source: str, **fields: Any) -> None:
        self.positions[source] = self.positions.get(source, 0) + 1
        self.events.append(Event(source=source, position=self.positions[source], partition=REE, **fields))

    def run(self, key: str, *path: str, source: str = "api-000001", **facts: Any) -> None:
        for current, target in pairwise([None, *path]):
            assert target is not None
            step = {"action": facts.get("action", "build_experiment_environment")}
            if target in {"succeeded", "failed", "canceled"}:
                step |= {"attempt_id": facts.get("attempt_id"), "failure_category": None}
            self._add(
                source,
                kind="transition",
                owner="api",
                subject="AuthorApiAction",
                key=key,
                source_state=current,
                target_state=target,
                facts=step,
            )

    def settle(self, key: str, current: str, target: str, attempt_id: str | None, source: str = "api-000001") -> None:
        self._add(
            source,
            kind="transition",
            owner="api",
            subject="AuthorApiAction",
            key=key,
            source_state=current,
            target_state=target,
            facts={"action": "build_experiment_environment", "attempt_id": attempt_id, "failure_category": None},
        )

    def attempt(
        self,
        key: str,
        outcome: str = "succeeded",
        *,
        captured: bool = True,
        completed: bool = True,
        changed: bool = True,
        dispatched_by: str | None = None,
        operation: str = "build_experiment_environment",
        failed_record: str | None = None,
        drift_found: tuple[str, ...] = (),
        drift_recorded: str | None = None,
        drift_after: tuple[str, ...] = (),
        commit: str | None = None,
    ) -> None:
        pending: dict[str, Any] = {"operation": operation, "run_id": "run-1", "scope": "author"}
        pending |= {"drift_found": list(drift_found)} | ({"drift_recorded": drift_recorded} if drift_recorded else {})
        if dispatched_by is not None:
            pending["dispatched_by"] = dispatched_by
        steps: list[tuple[str | None, str, dict[str, Any]]] = [(None, "pending", pending), ("pending", "executing", {})]
        if completed:
            steps.append(("executing", "completed", {"outcome": outcome, "drift_after": list(drift_after)}))
        if completed and failed_record is not None:
            steps.append(("completed", "capture_failed", {"error": "locked", "record": failed_record}))
        elif completed and captured:
            steps.append(("completed", "captured", {"commit": commit or "c" * 40, "changed": changed}))
        for current, target, facts in steps:
            self._add(
                "git:ree",
                kind="transition",
                owner="core",
                subject="Attempt",
                key=key,
                source_state=current,
                target_state=target,
                facts=facts,
            )

    def drift(self, key: str, path: str, part: str = "workspace", source: str = "environment-000001") -> None:
        self._add(
            source,
            kind="transition",
            owner="environment",
            subject="Drift",
            key=key,
            source_state=None,
            target_state="arisen",
            facts={"path": path, "part": part},
        )

    def undo(self, key: str, source: str = "environment-000001") -> None:
        self._add(
            source,
            kind="transition",
            owner="environment",
            subject="Drift",
            key=key,
            source_state="arisen",
            target_state="undone",
            facts={},
        )

    def bundle(self, key: str, *heads: str, source: str = "environment-000001") -> None:
        request = {"kind": "send", "message": "export_bundle", "facts": {}}
        answer = (
            {"kind": "receive", "message": "exported", "facts": {"heads": list(heads)}}
            if heads
            else {"kind": "receive", "message": "refused", "facts": {"exit": 1}}
        )
        for record in (request, answer):
            self._add(source, owner="environment", subject="export_bundle", key=key, **record)

    def command(self, key: str, source: str = "environment-000001", *, beside: str | None = None) -> str:
        facts = {"run_id": "run-1"}
        self._add(
            source, kind="send", owner="environment", subject="run_command", key=key, message="run_command", facts=facts
        )
        request = f"{source}#{self.positions[source]}"
        if beside is not None:
            self.drift(f"beside-{key}", beside, part="overlay", source=source)
        exited = {"exit": 0, "commit": f"c-{key}"}
        self._add(
            source, kind="receive", owner="environment", subject="run_command", key=key, message="exited", facts=exited
        )
        return request

    def start(self, key: str, *outcomes: tuple[str, str | None], source: str = "api-000001") -> str:
        self._add(
            source,
            kind="send",
            owner="supervisor",
            subject="start_run",
            key=key,
            message="start_run",
            facts={"operation": "build_experiment_environment", "run_id": "run-1", "session": "s1"},
        )
        request = f"{source}#{self.positions[source]}"
        for kind, message in outcomes:
            facts: dict[str, Any] = {"reason": "x"} if kind == "abandon" else {}
            self._add(source, kind=kind, owner="supervisor", subject="start_run", key=key, message=message, facts=facts)
        return request

    def follow(
        self,
        key: str,
        *outcomes: tuple[str, str | None],
        owner: str = "supervisor",
        commit: str | None = "c" * 40,
        status: str = "succeeded",
        record: str | None = None,
        source: str = "api-000001",
    ) -> None:
        self._add(
            source,
            kind="send",
            owner=owner,
            subject="follow_run",
            key=key,
            message="follow_run",
            facts={"run_id": "run-1", "session": "s1"},
        )
        for kind, message in outcomes:
            facts: dict[str, Any] = (
                {"status": status, "commit": commit} | ({"record": record} if record else {})
                if message == "settled"
                else ({"reason": "x"} if kind == "abandon" else {})
            )
            self._add(source, kind=kind, owner=owner, subject="follow_run", key=key, message=message, facts=facts)

    def execution(self, key: str, *path: str, start: str | None = None, source: str = "workbench-000001") -> None:
        for current, target in pairwise([start, *path]):
            assert target is not None
            facts: dict[str, Any] = (
                {"operation": "build_experiment_environment", "run_id": "run-1"} if current is None else {}
            )
            if target in {"exited", "stopped"}:
                facts |= {"exit_code": 0, "status": "succeeded"}
            if target == "stopped":
                facts["cause"] = "cancel"
            if target == "lost":
                facts |= {"status": "interrupted", "reason": "vanished"}
            self._add(
                source,
                kind="transition",
                owner="workbench",
                subject="Execution",
                key=key,
                source_state=current,
                target_state=target,
                facts=facts,
            )

    def session(
        self,
        key: str,
        *path: str,
        start: str | None = None,
        store: str = "lab-1",
        reason: str | None = None,
        source: str = "api-000001",
    ) -> None:
        for current, target in pairwise([start, *path]):
            assert target is not None
            facts: dict[str, Any] = {"workbench_id": f"bench-{key}", "nonce": f"n-{key}", "store_id": store}
            if target == "connected":
                facts |= {"arch": "x86_64", "slots": 1}
            if target in {"refused", "lost"}:
                facts["reason"] = reason
            self.positions[source] = self.positions.get(source, 0) + 1
            self.events.append(
                Event(
                    source=source,
                    position=self.positions[source],
                    partition=store,
                    kind="transition",
                    owner="supervisor",
                    subject="WorkbenchSession",
                    key=key,
                    source_state=current,
                    target_state=target,
                    facts=facts,
                )
            )

    def receipt(
        self, step: str, current: str | None, target: str, *, attempt_id: str | None, cause: str = "operation"
    ) -> None:
        self._add(
            "git:ree",
            kind="transition",
            owner="core",
            subject="Receipt",
            key=f"{REE}/{step}",
            source_state=current,
            target_state=target,
            facts={
                "step": step,
                "kind": step,
                "cause": cause,
                "operation": "build_experiment_environment",
                "attempt_id": attempt_id,
            },
        )


def verdicts(recorder: Recorder, *sources: Source) -> dict[str, str]:
    result = check(SPEC, Evidence(sources=sources or (journal(), bench(), git(REE)), events=tuple(recorder.events)))
    return {rule.rule: str(rule.verdict) for rule in result.rules} | {"overall": str(result.verdict)}


def findings(recorder: Recorder, rule: str, *sources: Source) -> list[str]:
    result = check(SPEC, Evidence(sources=sources or (journal(), bench(), git(REE)), events=tuple(recorder.events)))
    return [f"{f.verdict}: {f.reason}" for r in result.rules if r.rule == rule for f in r.findings]


def complete_command(recorder: Recorder, run: str = "run-1", attempt: str = "a1") -> None:
    recorder.run(run, "requested", "running")
    request = recorder.start(attempt, ("receive", "accepted"))
    recorder.execution(attempt, "started", "exited")
    recorder.attempt(attempt, dispatched_by=request)
    recorder.follow(attempt, ("receive", "settled"))
    recorder.settle(run, "running", "succeeded", attempt)


def test_a_complete_command_passes_every_rule_it_triggers() -> None:
    recorder = Recorder()
    complete_command(recorder)
    result = verdicts(recorder)
    assert result["overall"] == "passed"
    assert result["machine:Receipt"] == "not_triggered"


def test_no_triggered_behaviour_is_inconclusive_not_passed() -> None:
    assert verdicts(Recorder())["overall"] == "inconclusive"


def test_an_undeclared_transition_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "canceled")
    assert findings(recorder, "machine:AuthorApiAction") == ["violated: undeclared transition requested -> canceled"]


def test_a_discontinuous_history_is_violated_only_when_the_source_is_complete() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested")
    recorder._add(
        "api-000001",
        kind="transition",
        owner="api",
        subject="AuthorApiAction",
        key="run-1",
        source_state="running",
        target_state="canceling",
        facts={"action": "build_experiment_environment"},
    )
    assert findings(recorder, "machine:AuthorApiAction")[0].startswith(
        "violated: recorded running -> canceling after requested"
    )
    gappy = findings(recorder, "machine:AuthorApiAction", journal(complete=False), git(REE))
    assert gappy[0].startswith("inconclusive")


def test_a_run_left_active_when_the_api_closed_for_good_is_violated_but_not_across_a_restart() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running")
    final = journal().model_copy(update={"final": True})
    assert findings(recorder, "machine:AuthorApiAction", final, git(REE)) == [
        "violated: still running when api-000001 closed for good"
    ]
    assert verdicts(recorder, journal(), git(REE))["machine:AuthorApiAction"] == "passed"


def test_an_event_from_a_component_that_does_not_own_the_entity_is_violated() -> None:
    recorder = Recorder()
    recorder._add(
        "api-000001",
        kind="transition",
        owner="supervisor",
        subject="AuthorApiAction",
        key="run-1",
        source_state=None,
        target_state="requested",
        facts={"operation": "build_experiment_environment"},
    )
    assert "violated: recorded by supervisor, but api owns AuthorApiAction" in findings(
        recorder, "machine:AuthorApiAction"
    )


@pytest.mark.parametrize(
    ("outcomes", "reason"),
    [
        ((("receive", "accepted"), ("receive", "busy")), "2 outcomes for one request"),
        ((("receive", "start_run"),), "received start_run, which is not a response"),
        ((), "no outcome before api-000001 closed"),
    ],
)
def test_start_exchanges_have_exactly_one_outcome(outcomes: tuple[tuple[str, str | None], ...], reason: str) -> None:
    recorder = Recorder()
    recorder.start("a1", *outcomes)
    assert f"violated: {reason}" in findings(recorder, "boundary:start_run")


def test_an_abandoned_start_is_a_legal_outcome() -> None:
    recorder = Recorder()
    recorder.start("a1", ("abandon", None))
    assert verdicts(recorder)["boundary:start_run"] == "passed"


def test_a_command_is_followed_again_after_each_abandoned_follow() -> None:
    recorder = Recorder()
    recorder.follow("a1", ("abandon", None))
    recorder.follow("a1", ("abandon", None))
    recorder.follow("a1", ("receive", "settled"), commit=None, status="failed")
    assert verdicts(recorder)["boundary:follow_run"] == "passed"


def test_a_follow_sent_again_before_the_last_had_an_outcome_is_violated() -> None:
    recorder = Recorder()
    recorder.follow("a1")
    recorder.follow("a1", ("receive", "settled"), commit=None, status="failed")
    assert findings(recorder, "boundary:follow_run") == ["violated: sent again before api-000001#1 had an outcome"]


def test_a_follow_left_open_by_a_crashed_api_is_superseded_by_the_next_process() -> None:
    recorder = Recorder()
    recorder.follow("a1")
    recorder.follow("a1", ("receive", "settled"), commit=None, status="failed", source="api-000002")
    crashed = journal(closed=False)
    assert verdicts(recorder, crashed, journal("api-000002"), bench(), git(REE))["boundary:follow_run"] == "passed"


def test_an_outcome_without_a_follow_is_violated() -> None:
    recorder = Recorder()
    recorder.follow("a1", ("receive", "settled"), ("receive", "unknown"), commit=None, status="failed")
    assert findings(recorder, "boundary:follow_run") == ["violated: an outcome was recorded without a request"]


def test_an_accepted_start_without_an_executor_is_violated() -> None:
    recorder = Recorder()
    recorder.start("a1", ("receive", "accepted"))
    assert findings(recorder, "accepted-runs-started") == ["violated: Execution a1 was never recorded"]


def test_two_executors_in_one_ree_at_once_are_violated() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started")
    recorder.execution("a2", "started", "exited")
    recorder.execution("a3", "started", "exited")
    assert findings(recorder, "one-execution-per-ree") == [
        "violated: Execution a1 was started",
        "violated: Execution a1 was started",
    ]


def test_an_executor_after_the_last_one_ended_is_allowed() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started", "adopted", "exited")
    recorder.execution("a2", "started", "exited")
    assert verdicts(recorder)["one-execution-per-ree"] == "passed"


def test_a_lost_executor_settles_its_attempt_as_interrupted() -> None:
    recorder = Recorder()
    recorder.attempt("a1", "interrupted", changed=False)
    recorder.execution("a1", "started", "lost")
    found = verdicts(recorder)
    assert found["lost-executions-settle-their-attempt"] == "passed"
    assert found["canceled-attempts-change-nothing"] == "passed"


def test_a_lost_executor_whose_attempt_is_left_executing_is_not_settled() -> None:
    recorder = Recorder()
    recorder.attempt("a1", completed=False)
    recorder.execution("a1", "started", "lost")
    assert findings(recorder, "lost-executions-settle-their-attempt") == ["inconclusive: Attempt a1 is still executing"]


def test_an_interrupted_attempt_that_changed_the_ree_is_violated() -> None:
    recorder = Recorder()
    recorder.attempt("a1", "interrupted", changed=True)
    assert findings(recorder, "canceled-attempts-change-nothing") == [
        "violated: completed -> captured with {'changed': True}"
    ]


def test_an_executor_left_running_is_taken_over_by_the_next_workbench_process() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started")
    recorder.execution("a1", "adopted", start="started", source="workbench-000002")
    recorder.execution("a1", "exited", start="adopted", source="workbench-000002")
    found = verdicts(recorder, journal(), bench(), bench("workbench-000002"), git(REE))
    assert found["machine:Execution"] == "passed"


def test_an_executor_the_next_workbench_process_never_takes_over_is_violated() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started")
    found = findings(recorder, "machine:Execution", journal(), bench(), bench("workbench-000002"), git(REE))
    assert found == ["violated: still started when workbench-000002, a later journal of its owner, closed"]


def test_an_executor_the_next_workbench_process_does_not_take_over_first_is_violated() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started")
    recorder._add(
        "workbench-000002",
        kind="transition",
        owner="workbench",
        subject="Execution",
        key="a1",
        source_state="started",
        target_state="started",
        facts={},
    )
    found = findings(recorder, "machine:Execution", journal(), bench(), bench("workbench-000002"), git(REE))
    assert "violated: workbench-000002 took it over with started -> started" in found


def test_an_executor_left_running_by_a_closed_journal_is_open_until_the_next_one_closes() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started")
    found = verdicts(recorder, journal(), bench(), bench("workbench-000002", closed=False), git(REE))
    assert found["machine:Execution"] == "passed"


def test_an_executor_still_running_when_its_store_closed_for_good_is_violated() -> None:
    recorder = Recorder()
    recorder.execution("a1", "started")
    final = bench().model_copy(update={"final": True})
    assert findings(recorder, "machine:Execution", journal(), final, git(REE)) == [
        "violated: still started when workbench-000001 closed for good"
    ]


def test_an_action_left_running_by_the_api_is_resumed_by_the_next_api_process() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running")
    recorder.settle("run-1", "running", "resumed", None, source="api-000002")
    recorder.settle("run-1", "resumed", "failed", None, source="api-000002")
    found = verdicts(recorder, journal(), journal("api-000002"), bench(), git(REE))
    assert found["machine:AuthorApiAction"] == "passed"


def test_a_request_left_open_by_a_crashed_api_ended_with_it() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", action="view_action")
    found = verdicts(recorder, journal(closed=False), journal("api-000002"), bench(), git(REE))
    assert found["machine:AuthorApiAction"] == "passed"


def test_an_action_the_next_api_process_leaves_open_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running")
    found = findings(recorder, "machine:AuthorApiAction", journal(), journal("api-000002"), bench(), git(REE))
    assert found == ["violated: still running when api-000002, a later journal of its owner, closed"]


def test_success_without_a_captured_attempt_is_violated_when_git_covers_the_ree() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="missing")
    recorder.attempt("other")
    assert findings(recorder, "api-success-is-recorded") == ["violated: Attempt missing was never recorded"]


def test_success_without_git_evidence_for_the_ree_is_inconclusive() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="missing")
    assert findings(recorder, "api-success-is-recorded", journal(), git("another-ree")) == [
        "inconclusive: no git evidence from core covers ree-1"
    ]


def test_success_backed_by_a_failed_attempt_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1", outcome="failed")
    assert findings(recorder, "api-success-is-recorded") == [
        "violated: Attempt a1 reached captured with {'outcome': 'failed'}"
    ]


def test_a_success_without_an_attempt_id_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded")
    assert findings(recorder, "api-success-is-recorded") == ["violated: has no attempt_id"]


def test_workbench_actions_need_no_attempt() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", action="create_ree")
    assert verdicts(recorder)["api-success-is-recorded"] == "not_triggered"


def test_an_attempt_never_captured_is_violated_once_the_evidence_covers_the_result() -> None:
    recorder = Recorder()
    recorder.follow("a1", ("receive", "settled"))
    recorder.attempt("a1", captured=False)
    expected = "violated: Attempt a1 is still completed, not captured"
    assert findings(recorder, "follow-success-is-captured") == [expected]


def test_an_attempt_still_open_when_its_history_was_taken_is_inconclusive() -> None:
    recorder = Recorder()
    recorder.follow("a1", ("receive", "settled"))
    recorder.attempt("a1", captured=False)
    taken = git(REE, cut={"api-000001": (1, 1)})
    assert findings(recorder, "follow-success-is-captured", journal(), taken) == [
        "inconclusive: Attempt a1 is still completed"
    ]


def canceled_run(recorder: Recorder, **attempt: Any) -> None:
    recorder.run("run-1", "requested", "running")
    request = recorder.start("a1", ("receive", "accepted"))
    recorder.execution("a1", "started", "stopped")
    recorder.attempt("a1", "canceled", dispatched_by=request, **attempt)
    recorder.follow("a1", ("receive", "settled"), status="canceled")
    recorder.settle("run-1", "running", "canceling", "a1")
    recorder.settle("run-1", "canceling", "canceled", "a1")


def test_a_canceled_run_settles_its_attempt_before_it_reports() -> None:
    recorder = Recorder()
    canceled_run(recorder, changed=False)
    found = verdicts(recorder)
    assert found["settled-api-actions-settle-their-attempt"] == "passed"
    assert found["canceled-attempts-change-nothing"] == "passed"


def test_a_run_that_abandons_its_attempt_mid_execution_is_violated() -> None:
    recorder = Recorder()
    canceled_run(recorder, completed=False)
    assert findings(recorder, "settled-api-actions-settle-their-attempt") == [
        "violated: Attempt a1 is still executing, not captured or capture_failed"
    ]


def test_a_failed_run_without_an_attempt_does_not_trigger_the_rule() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running")
    recorder.settle("run-1", "running", "failed", None)
    assert verdicts(recorder)["settled-api-actions-settle-their-attempt"] == "not_triggered"


def test_a_canceled_attempt_that_changed_the_ree_is_violated() -> None:
    recorder = Recorder()
    canceled_run(recorder, changed=True)
    assert findings(recorder, "canceled-attempts-change-nothing") == [
        "violated: completed -> captured with {'changed': True}"
    ]


def test_an_attempt_without_a_dispatch_is_violated() -> None:
    recorder = Recorder()
    recorder.attempt("a1")
    assert findings(recorder, "example-execution-was-dispatched") == ["violated: no start_run.start_run a1"]


def test_evidence_from_a_successful_attempt_passes() -> None:
    recorder = Recorder()
    recorder.receipt("build_experiment_environment", None, "missing", attempt_id=None, cause="baseline")
    recorder.attempt("a1")
    recorder.receipt("build_experiment_environment", "missing", "current", attempt_id="a1")
    assert verdicts(recorder)["receipts-come-from-their-producers"] == "passed"


def test_evidence_from_a_failed_attempt_is_violated() -> None:
    recorder = Recorder()
    recorder.receipt("build_experiment_environment", None, "missing", attempt_id=None, cause="baseline")
    recorder.attempt("a1", outcome="failed")
    recorder.receipt("build_experiment_environment", "missing", "current", attempt_id="a1")
    assert verdicts(recorder)["receipts-come-from-their-producers"] == "violated"


def test_evidence_from_an_operation_that_does_not_produce_it_is_violated() -> None:
    recorder = Recorder()
    recorder.receipt("build_experiment_environment", None, "missing", attempt_id=None, cause="baseline")
    recorder.attempt("a1", operation="write_script")
    recorder.receipt("build_experiment_environment", "missing", "current", attempt_id="a1")
    assert findings(recorder, "receipts-come-from-their-producers") == [
        "violated: Attempt a1 reached captured with {'outcome': 'succeeded', 'operation': 'write_script'}"
    ]


def test_evidence_restored_by_a_bundle_load_passes_for_every_kind() -> None:
    recorder = Recorder()
    recorder.attempt("a1", operation="load_ree_bundle")
    for step in ("acquire_source", "build_experiment_environment", "activate_experiment_environment"):
        recorder.receipt(step, None, "missing", attempt_id=None, cause="baseline")
        recorder.receipt(step, "missing", "current", attempt_id="a1")
    assert verdicts(recorder)["receipts-come-from-their-producers"] == "passed"


def test_evidence_going_stale_and_current_again_is_not_appearing() -> None:
    recorder = Recorder()
    recorder.receipt("build_experiment_environment", None, "current", attempt_id=None, cause="baseline")
    recorder.attempt("a1", outcome="failed")
    recorder.receipt("build_experiment_environment", "current", "stale", attempt_id="a1")
    recorder.receipt("build_experiment_environment", "stale", "current", attempt_id="a1")
    assert verdicts(recorder)["receipts-come-from-their-producers"] == "not_triggered"


def test_an_entity_without_a_machine_still_has_its_records_checked_but_covers_nothing() -> None:
    recorder = Recorder()
    recorder.receipt("build_experiment_environment", None, "stale", attempt_id=None, cause="baseline")
    recorder.receipt("build_experiment_environment", "stale", "not_applicable", attempt_id=None, cause="external")
    recorder.receipt("build_experiment_environment", "missing", "current", attempt_id=None, cause="external")
    assert findings(recorder, "machine:Receipt") == ["violated: recorded missing -> current after not_applicable"]
    result = check(SPEC, Evidence(sources=(journal(), git(REE)), events=tuple(recorder.events)))
    assert result.coverage.transitions["Receipt"] == {}


def test_a_journal_is_judged_by_what_it_holds_not_by_the_vocabulary_it_names() -> None:
    recorder = Recorder()
    complete_command(recorder)
    older = journal().model_copy(update={"vocabulary": "sha256:old"})
    assert verdicts(recorder, older, bench(), git(REE))["overall"] == "passed"


def test_what_owners_record_beyond_the_vocabulary_is_reported_and_never_judged() -> None:
    recorder = Recorder()
    complete_command(recorder)
    recorder._add(
        "api-000001",
        kind="transition",
        owner="api",
        subject="Deposit",
        key="d1",
        source_state=None,
        target_state="started",
        facts={},
    )
    recorder._add(
        "api-000001",
        kind="transition",
        owner="api",
        subject="AuthorApiAction",
        key="run-2",
        source_state=None,
        target_state="requested",
        facts={"action": "build_experiment_environment", "queue": "fast"},
    )
    recorder.settle("run-2", "requested", "failed", None)
    result = check(SPEC, Evidence(sources=(journal(), bench(), git(REE)), events=tuple(recorder.events)))
    assert result.verdict == "passed"
    assert [(extra.subject, extra.fact, extra.count) for extra in result.extras] == [
        ("AuthorApiAction", "queue", 1),
        ("Deposit", None, 1),
    ]
    model, _, _ = replay(SPEC, Evidence(sources=(journal(), bench(), git(REE)), events=tuple(recorder.events)))
    assert "queue" not in model.instances["AuthorApiAction"]["run-2"].facts


def test_a_missing_required_fact_leaves_the_machine_inconclusive() -> None:
    recorder = Recorder()
    recorder._add(
        "api-000001",
        kind="transition",
        owner="api",
        subject="AuthorApiAction",
        key="run-1",
        source_state=None,
        target_state="requested",
        facts={"queue": "fast"},
    )
    recorder.settle("run-1", "requested", "failed", None)
    assert findings(recorder, "machine:AuthorApiAction") == ["inconclusive: missing required facts ['action']"]


def test_a_declared_fact_of_another_type_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "failed", action=7)
    assert findings(recorder, "machine:AuthorApiAction") == ["violated: fact 'action' is not str"] * 2


def test_a_message_missing_a_required_fact_leaves_the_exchange_inconclusive() -> None:
    recorder = Recorder()
    recorder.follow("a1")
    recorder._add(
        "api-000001",
        kind="receive",
        owner="supervisor",
        subject="follow_run",
        key="a1",
        message="settled",
        facts={"commit": "c" * 40},
    )
    assert findings(recorder, "boundary:follow_run") == ["inconclusive: missing required facts ['status']"]


def test_transitions_recorded_against_a_boundary_are_violated() -> None:
    recorder = Recorder()
    complete_command(recorder)
    recorder._add(
        "api-000001",
        kind="transition",
        owner="supervisor",
        subject="start_run",
        key="a1",
        source_state=None,
        target_state="sent",
        facts={},
    )
    assert findings(recorder, "boundary:start_run") == ["violated: transitions recorded against a boundary"]


def test_a_journal_of_a_process_the_vocabulary_does_not_place_is_not_judged() -> None:
    recorder = Recorder()
    complete_command(recorder)
    provider = Source(
        id="provider-000001",
        kind="journal",
        process="provider",
        rank=1,
        hosts=frozenset({"provider"}),
        complete=True,
        closed=True,
    )
    assert verdicts(recorder, journal(), bench(), git(REE), provider)["evidence"] == "passed"


def judgements(recorder: Recorder) -> list[tuple[str, str, str]]:
    model, _, _ = replay(SPEC, Evidence(sources=(journal(), bench(), git(REE)), events=tuple(recorder.events)))
    return [(j.rule, j.event, j.verdict) for j in judge_occurrences(model)]


def test_each_occurrence_is_judged_at_the_event_that_triggered_it() -> None:
    recorder = Recorder()
    complete_command(recorder)
    found = judgements(recorder)
    settled = next(e for e in recorder.events if e.subject == "AuthorApiAction" and e.target_state == "succeeded")
    assert ("api-success-is-recorded", settled.ref, "passed") in found
    model, _, _ = replay(SPEC, Evidence(sources=(journal(), bench(), git(REE)), events=tuple(recorder.events)))
    captured = next(j for j in judge_occurrences(model) if j.rule == "example-execution-was-dispatched")
    assert (captured.subject, captured.key) == ("Attempt", "a1")
    assert {verdict for _, _, verdict in found} == {"passed"}


def test_occurrence_verdicts_agree_with_the_rule_verdicts() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1", outcome="failed")
    rules = verdicts(recorder)
    for rule, _, verdict in judgements(recorder):
        assert verdict == rules[rule] or (verdict == "passed" and rules[rule] != "not_triggered")
    assert ("api-success-is-recorded", "api-000001#3", "violated") in judgements(recorder)


@pytest.mark.parametrize(
    ("cut", "expected"),
    [
        ((3, 4), "violated: Attempt missing was never recorded"),
        ((2, 3), "inconclusive: api-000001#3 was recorded while git:ree was taken"),
        ((1, 2), "inconclusive: api-000001#3 was recorded after git:ree was taken"),
    ],
)
def test_a_snapshot_must_hold_only_what_happened_before_it_was_taken(cut: tuple[int, int], expected: str) -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="missing")
    recorder.attempt("other")
    sources = (journal(closed=False), git(REE, cut={"api-000001": cut}))
    assert findings(recorder, "api-success-is-recorded", *sources) == [expected]


def test_a_snapshot_cannot_vouch_for_a_journal_it_was_not_cut_against() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="missing")
    recorder.attempt("other")
    sources = (journal(closed=False), git(REE, cut={"workbench-000001": (5, 6)}))
    assert findings(recorder, "api-success-is-recorded", *sources) == [
        "inconclusive: the evidence cannot place api-000001#3 against when git:ree was taken"
    ]


def observed(recorder: Recorder, state: str) -> None:
    recorder.events.append(
        Event(
            source="stores",
            position=1,
            kind="observed",
            owner="api",
            subject="AuthorApiAction",
            key="run-1",
            partition=REE,
            target_state=state,
        )
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("running", []),
        ("succeeded", []),
        (
            "requested",
            ["violated: persisted as requested, but around stores the journal shows ['running', 'succeeded']"],
        ),
    ],
)
def test_a_live_store_snapshot_holds_a_state_reached_around_its_cut(state: str, expected: list[str]) -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1")
    observed(recorder, state)
    sources = (journal(closed=False), git(REE), stores(cut={"api-000001": (2, 2)}))
    assert findings(recorder, "reconciliation", *sources) == expected


def test_a_live_store_snapshot_after_a_restart_is_placed_by_each_events_own_epoch() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="a1", source="api-000002")
    recorder.attempt("a1")
    observed(recorder, "succeeded")
    restarted = (journal("api-000001"), journal("api-000002", closed=False), git(REE))
    assert (
        findings(recorder, "reconciliation", *restarted, stores(cut={"api-000001": (9, 9), "api-000002": (2, 2)})) == []
    )
    earlier = Recorder()
    earlier.run("run-1", "requested", "running", "succeeded", attempt_id="a1")
    earlier.attempt("a1")
    observed(earlier, "succeeded")
    assert findings(earlier, "reconciliation", *restarted, stores(cut={"api-000002": (1, 1)})) == []


def without(recorder: Recorder, state: str, fact: str) -> None:
    recorder.events = [
        event.model_copy(update={"facts": {k: v for k, v in event.facts.items() if k != fact}})
        if event.subject == "Attempt" and event.target_state == state
        else event
        for event in recorder.events
    ]


def test_a_condition_on_a_fact_the_record_lacks_is_inconclusive_not_violated() -> None:
    recorder = Recorder()
    complete_command(recorder)
    without(recorder, "completed", "outcome")
    assert findings(recorder, "api-success-is-recorded") == [
        "inconclusive: Attempt a1 reached captured without outcome"
    ]
    canceled = Recorder()
    canceled.attempt("a1", "canceled")
    without(canceled, "captured", "changed")
    assert findings(canceled, "canceled-attempts-change-nothing") == [
        "inconclusive: completed -> captured without changed"
    ]


def test_a_source_writes_its_sets_in_a_stable_order() -> None:
    source = journal().model_copy(update={"hosts": frozenset({"supervisor", "core", "api"})})
    assert source.model_dump(mode="json")["hosts"] == ["api", "core", "supervisor"]


def test_a_store_snapshot_after_the_owners_stopped_must_match_exactly() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1")
    observed(recorder, "running")
    assert findings(recorder, "reconciliation", journal(), git(REE), stores()) == [
        "violated: persisted as running, but the journal replays to succeeded"
    ]


def test_without_citations_the_order_across_sources_is_unknown() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running")
    recorder.start("a1", ("receive", "accepted"))
    recorder.execution("a1", "started", "exited")
    recorder.follow("a1", ("receive", "settled"), commit=None)
    recorder.attempt("a1")
    recorder.settle("run-1", "running", "succeeded", "a1")
    result = verdicts(recorder)
    assert result["example-execution-was-dispatched"] == "inconclusive"
    assert result["follow-success-is-captured"] == "inconclusive"
    assert result["api-success-is-recorded"] == "inconclusive"
    assert findings(recorder, "example-execution-was-dispatched") == [
        "inconclusive: the evidence cannot order start_run.start_run a1 against it"
    ]


def failed_capture(recorder: Recorder, *, named: str | None, recorded: str = "sha256:" + "f" * 64) -> None:
    recorder.run("run-1", "requested", "running")
    recorder.follow("a1", ("receive", "settled"), commit=None, status="failed", record=named)
    recorder.attempt("a1", failed_record=recorded)
    recorder.settle("run-1", "running", "failed", "a1")


def test_a_failed_capture_is_ordered_by_the_record_its_result_names() -> None:
    cited = Recorder()
    failed_capture(cited, named="sha256:" + "f" * 64)
    assert verdicts(cited)["settled-api-actions-settle-their-attempt"] == "passed"
    uncited = Recorder()
    failed_capture(uncited, named=None)
    assert verdicts(uncited)["settled-api-actions-settle-their-attempt"] == "inconclusive"


def test_a_result_naming_another_record_than_the_failed_capture_left_is_violated() -> None:
    recorder = Recorder()
    failed_capture(recorder, named="sha256:" + "e" * 64)
    assert findings(recorder, "boundary:follow_run") == [
        f"violated: names sha256:{'e' * 64}, but the evidence records ['sha256:{'f' * 64}']"
    ]


def test_a_citation_of_a_record_the_evidence_does_not_hold_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "requested", "running")
    recorder.start("a1", ("receive", "accepted"))
    recorder.follow("a1", ("receive", "settled"), commit="d" * 40)
    recorder.attempt("a1", dispatched_by="api-000001#99")
    recorder.settle("run-1", "running", "succeeded", "a1")
    assert findings(recorder, "boundary:start_run") == [
        "violated: names api-000001#99, but the evidence records ['api-000001#3']",
    ]
    assert findings(recorder, "boundary:follow_run") == [
        f"violated: names {'d' * 40}, but the evidence records ['{'c' * 40}']",
    ]


def test_a_store_is_served_by_one_session_at_a_time() -> None:
    recorder = Recorder()
    recorder.session("s1", "opened", "connected")
    recorder.session("s2", "opened", "refused", reason="store_claimed")
    recorder.session("s1", "lost", start="connected", reason="closed")
    recorder.session("s3", "opened", "connected")
    recorder.session("s3", "lost", start="connected", reason="shutdown")
    recorder.session("other", "opened", "connected", store="lab-2")
    recorder.session("other", "lost", start="connected", store="lab-2", reason="shutdown")
    result = verdicts(recorder)
    assert (result["one-session-per-store"], result["machine:WorkbenchSession"]) == ("passed", "passed")


def test_a_second_session_admitted_beside_the_first_is_violated() -> None:
    recorder = Recorder()
    recorder.session("s1", "opened", "connected")
    recorder.session("s2", "opened", "connected")
    recorder.session("s1", "lost", start="connected", reason="closed")
    recorder.session("s2", "lost", start="connected", reason="closed")
    assert findings(recorder, "one-session-per-store") == ["violated: WorkbenchSession s1 was connected"]


def test_a_session_still_connected_when_the_journal_closed_is_violated_but_open_one_is_not() -> None:
    recorder = Recorder()
    recorder.session("s1", "opened", "connected")
    assert findings(recorder, "machine:WorkbenchSession") == ["violated: still connected when api-000001 closed"]
    assert verdicts(recorder, journal(closed=False), git(REE))["machine:WorkbenchSession"] == "passed"


def test_a_session_ends_with_the_api_process_that_crashed_holding_it() -> None:
    recorder = Recorder()
    recorder.session("s1", "opened", "connected")
    recorder.session("s2", "opened", "connected", source="api-000002")
    recorder.session("s2", "lost", start="connected", reason="closed", source="api-000002")
    crashed = (journal("api-000001", closed=False), journal("api-000002"), git(REE))
    result = verdicts(recorder, *crashed)
    assert (result["one-session-per-store"], result["machine:WorkbenchSession"]) == ("passed", "passed")


def test_a_start_names_the_session_it_was_sent_on() -> None:
    recorder = Recorder()
    complete_command(recorder)
    recorder.events = [
        event.model_copy(update={"facts": {k: v for k, v in event.facts.items() if k != "session"}})
        if event.message == "start_run"
        else event
        for event in recorder.events
    ]
    assert findings(recorder, "boundary:start_run") == ["inconclusive: missing required facts ['session']"]


DRIFT = "drift-is-found-by-the-next-attempt"


def test_the_attempt_after_a_drift_names_the_file_and_holds() -> None:
    recorder = Recorder()
    recorder.drift("d1", "workspace/run.sh")
    command = recorder.command("a1")
    recorder.attempt("a1", "failed", dispatched_by=command, drift_found=("workspace/run.sh",), commit="c-a1")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "passed"


def test_an_attempt_after_a_drift_that_does_not_name_it_is_violated() -> None:
    recorder = Recorder()
    recorder.attempt("a0", dispatched_by=recorder.command("a0"), commit="c-a0")
    recorder.drift("d1", "workspace/run.sh")
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")

    assert findings(recorder, DRIFT, environment(), git(REE)) == [
        "violated: Attempt a1, the first after it, reached pending with {'drift_found': []}"
    ]


def test_a_drift_no_attempt_follows_holds() -> None:
    recorder = Recorder()
    recorder.attempt("a0", dispatched_by=recorder.command("a0"), commit="c-a0")
    recorder.drift("d1", "workspace/run.sh")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "passed"


def test_an_attempt_that_records_an_edit_before_the_command_runs_is_the_next_one() -> None:
    recorder = Recorder()
    recorder.drift("d1", "overlay/ree-scripts/launch.sh", part="overlay")
    command = recorder.command("a1")
    edit = ("overlay/ree-scripts/launch.sh",)
    recorder.attempt("e1", dispatched_by=command, operation="write_script", drift_found=edit, drift_recorded=edit[0])
    recorder.attempt("a1", dispatched_by=command)

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "passed"


def test_an_attempt_the_evidence_cannot_order_against_a_drift_is_inconclusive() -> None:
    recorder = Recorder()
    recorder.drift("d1", "workspace/run.sh")
    recorder.attempt("a1")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "inconclusive"


def test_a_drift_while_an_attempt_runs_that_the_attempt_names_after_its_handler_holds() -> None:
    recorder = Recorder()
    command = recorder.command("a1", beside="overlay/ree-scripts/launch.sh")
    recorder.attempt("a1", dispatched_by=command, drift_after=("overlay/ree-scripts/launch.sh",), commit="c-a1")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "passed"


def test_a_drift_while_an_attempt_runs_that_it_does_not_name_cannot_be_placed_against_it() -> None:
    recorder = Recorder()
    command = recorder.command("a1", beside="overlay/ree-scripts/launch.sh")
    recorder.attempt("a1", dispatched_by=command, commit="c-a1")
    recorder.attempt("a2", dispatched_by=recorder.command("a2"), commit="c-a2")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "inconclusive"


def test_an_attempt_that_names_a_drift_after_its_handler_is_not_the_first_after_it() -> None:
    recorder = Recorder()
    recorder.drift("d1", "overlay/ree-scripts/launch.sh", part="overlay")
    command = recorder.command("a1")
    recorder.attempt("a1", dispatched_by=command, drift_after=("overlay/ree-scripts/launch.sh",), commit="c-a1")

    assert findings(recorder, DRIFT, environment(), git(REE)) == [
        "violated: Attempt a1, the first after it, reached pending with {'drift_found': []}"
    ]


def test_a_drift_undone_before_the_next_attempt_owes_it_nothing() -> None:
    recorder = Recorder()
    recorder.drift("d1", ".git/refs/heads/ree-history", part="history")
    recorder.undo("d1")
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "passed"


def test_a_drift_undone_only_after_an_attempt_missed_it_is_still_violated() -> None:
    recorder = Recorder()
    recorder.drift("d1", ".git/refs/heads/ree-history", part="history")
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")
    recorder.undo("d1")

    assert verdicts(recorder, environment(), git(REE))[DRIFT] == "violated"


BUNDLE = "bundles-carry-what-attempts-captured"


def test_a_bundle_ending_in_a_captured_commit_holds() -> None:
    recorder = Recorder()
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")
    recorder.bundle("b1", "c-a1")

    assert verdicts(recorder, environment(), git(REE))[BUNDLE] == "passed"


def test_a_bundle_ending_in_a_commit_no_attempt_captured_is_violated() -> None:
    recorder = Recorder()
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")
    recorder.drift("d1", ".git/refs/heads/ree-history", part="history")
    recorder.bundle("b1", "c-by-hand")

    assert findings(recorder, BUNDLE, environment(), git(REE)) == [
        "violated: names c-by-hand, which no Attempt reached captured with as its commit"
    ]


def test_a_bundle_is_held_to_each_history_it_carries() -> None:
    recorder = Recorder()
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")
    recorder.bundle("b1", "c-a1", "c-review-by-hand")

    assert verdicts(recorder, environment(), git(REE))[BUNDLE] == "violated"


def test_a_bundle_ending_in_a_commit_captured_only_after_it_is_violated() -> None:
    recorder = Recorder()
    recorder.bundle("b1", "c-a1")
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")

    assert findings(recorder, BUNDLE, environment(), git(REE)) == [
        "violated: Attempt reaching captured with commit c-a1 happened only after it"
    ]


def test_a_bundle_without_git_evidence_for_the_ree_is_inconclusive() -> None:
    recorder = Recorder()
    recorder.bundle("b1", "c-by-hand")

    assert verdicts(recorder, environment())[BUNDLE] == "inconclusive"


def test_a_refused_bundle_carries_nothing() -> None:
    recorder = Recorder()
    recorder.attempt("a1", dispatched_by=recorder.command("a1"), commit="c-a1")
    recorder.bundle("b1")

    assert verdicts(recorder, environment(), git(REE))[BUNDLE] == "not_triggered"


def test_the_transitions_covered_are_also_counted_in_each_partition_they_were_recorded_in() -> None:
    recorder = Recorder()
    complete_command(recorder)
    complete_command(recorder, "run-2", "a2")
    events = tuple(
        event.model_copy(update={"partition": "elsewhere"})
        if event.subject == "Attempt" and event.key == "a2"
        else event
        for event in recorder.events
    )
    result = check(SPEC, Evidence(sources=(journal(), bench(), git(REE)), events=events))

    covered = {move: count for move, count in result.coverage.transitions["Attempt"].items() if count}
    assert result.coverage.partitions["Attempt"] == {
        "elsewhere": dict.fromkeys(covered, 1),
        REE: dict.fromkeys(covered, 1),
    }
    assert all(count == 2 for count in covered.values())
