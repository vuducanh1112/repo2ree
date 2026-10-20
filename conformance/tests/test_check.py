"""Each rule separates violations, which complete evidence proves, from what it cannot decide."""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import pytest

from repo2ree_conformance.check import check, judge_occurrences, replay
from repo2ree_conformance.evidence import Event, Evidence, Source
from repo2ree_conformance.files import load_spec

SPEC = load_spec()
REE = "ree-1"


def journal(
    source_id: str = "api-000001", *, closed: bool = True, complete: bool = True, digest: str | None = None
) -> Source:
    return Source(
        id=source_id,
        kind="journal",
        process="api",
        rank=int(source_id.rsplit("-", 1)[1]),
        hosts=frozenset({"api", "supervisor"}),
        complete=complete,
        closed=closed,
        spec_digest=digest or SPEC.digest,
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
    """Builds owner-ordered events the way journals and the Git adapter number them."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.positions: dict[str, int] = {}

    def _add(self, source: str, **fields: Any) -> None:
        self.positions[source] = self.positions.get(source, 0) + 1
        self.events.append(Event(source=source, position=self.positions[source], partition=REE, **fields))

    def run(self, key: str, *path: str, source: str = "api-000001", **facts: Any) -> None:
        for current, target in pairwise([None, *path]):
            assert target is not None
            step = {"operation": facts.get("operation", "build")} if current is None else {}
            if target in {"succeeded", "failed", "canceled"}:
                step = {"attempt_id": facts.get("attempt_id"), "failure_category": None}
            self._add(
                source,
                kind="transition",
                owner="api",
                subject="Run",
                key=key,
                source_state=current,
                target_state=target,
                facts=step,
            )

    def settle(self, key: str, current: str, target: str, attempt_id: str | None) -> None:
        self._add(
            "api-000001",
            kind="transition",
            owner="api",
            subject="Run",
            key=key,
            source_state=current,
            target_state=target,
            facts={"attempt_id": attempt_id, "failure_category": None},
        )

    def attempt(
        self, key: str, outcome: str = "succeeded", *, captured: bool = True, dispatched_by: str | None = None
    ) -> None:
        pending: dict[str, Any] = {"operation": "build_runtime"}
        if dispatched_by is not None:
            pending["dispatched_by"] = dispatched_by
        steps: list[tuple[str | None, str, dict[str, Any]]] = [
            (None, "pending", pending),
            ("pending", "executing", {}),
            ("executing", "completed", {"outcome": outcome}),
        ]
        if captured:
            steps.append(("completed", "captured", {"commit": "c" * 40, "changed": True}))
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

    def dispatch(
        self, key: str, *outcomes: tuple[str, str | None], owner: str = "supervisor", commit: str | None = "c" * 40
    ) -> str:
        """Record an exchange; returns the request's reference, which the attempt cites."""
        self._add(
            "api-000001",
            kind="send",
            owner=owner,
            subject="dispatch",
            key=key,
            message="exec_action",
            facts={"operation": "build_runtime", "run_id": "run-1"},
        )
        request = f"api-000001#{self.positions['api-000001']}"
        for kind, message in outcomes:
            facts: dict[str, Any] = (
                {"status": "succeeded", "commit": commit}
                if message == "result"
                else ({"reason": "x"} if kind == "abandon" else {})
            )
            self._add("api-000001", kind=kind, owner=owner, subject="dispatch", key=key, message=message, facts=facts)
        return request


def verdicts(recorder: Recorder, *sources: Source) -> dict[str, str]:
    result = check(SPEC, Evidence(sources=sources or (journal(), git(REE)), events=tuple(recorder.events)))
    return {rule.rule: str(rule.verdict) for rule in result.rules} | {"overall": str(result.verdict)}


def findings(recorder: Recorder, rule: str, *sources: Source) -> list[str]:
    result = check(SPEC, Evidence(sources=sources or (journal(), git(REE)), events=tuple(recorder.events)))
    return [f"{f.verdict}: {f.reason}" for r in result.rules if r.rule == rule for f in r.findings]


def complete_command(recorder: Recorder, run: str = "run-1", attempt: str = "a1") -> None:
    recorder.run(run, "queued", "running")
    request = recorder.dispatch(attempt, ("receive", "result"))
    recorder.attempt(attempt, dispatched_by=request)
    recorder.settle(run, "running", "succeeded", attempt)


def test_a_complete_command_passes_every_rule_it_triggers() -> None:
    recorder = Recorder()
    complete_command(recorder)
    result = verdicts(recorder)
    assert result["overall"] == "passed"
    assert result["machine:Allocation"] == result["allocation-ends"] == "not_triggered"


def test_no_triggered_behaviour_is_inconclusive_not_passed() -> None:
    assert verdicts(Recorder())["overall"] == "inconclusive"


def test_an_undeclared_transition_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "succeeded")
    assert findings(recorder, "machine:Run") == ["violated: undeclared transition queued -> succeeded"]


def test_a_discontinuous_history_is_violated_only_when_the_source_is_complete() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued")
    recorder._add(
        "api-000001",
        kind="transition",
        owner="api",
        subject="Run",
        key="run-1",
        source_state="running",
        target_state="canceling",
        facts={},
    )
    assert findings(recorder, "machine:Run")[0].startswith("violated: recorded running -> canceling after queued")
    gappy = findings(recorder, "machine:Run", journal(complete=False), git(REE))
    assert gappy[0].startswith("inconclusive")


def test_a_run_left_active_in_a_closed_journal_is_violated_but_open_one_is_not() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running")
    assert findings(recorder, "machine:Run") == ["violated: still running when api-000001 closed"]
    assert verdicts(recorder, journal(closed=False), git(REE))["machine:Run"] == "passed"


def test_an_event_from_a_component_that_does_not_own_the_entity_is_violated() -> None:
    recorder = Recorder()
    recorder._add(
        "api-000001",
        kind="transition",
        owner="supervisor",
        subject="Run",
        key="run-1",
        source_state=None,
        target_state="queued",
        facts={"operation": "build"},
    )
    assert "violated: recorded by supervisor, but api owns Run" in findings(recorder, "machine:Run")


@pytest.mark.parametrize(
    ("outcomes", "reason"),
    [
        ((("receive", "result"), ("receive", "result")), "2 outcomes for one request"),
        ((("receive", "exec_action"),), "received exec_action, which is not a response"),
        ((), "no outcome before api-000001 closed"),
    ],
)
def test_dispatch_exchanges_have_exactly_one_outcome(outcomes: tuple[tuple[str, str | None], ...], reason: str) -> None:
    recorder = Recorder()
    recorder.dispatch("a1", *outcomes)
    assert f"violated: {reason}" in findings(recorder, "boundary:dispatch")


def test_an_abandoned_dispatch_is_a_legal_outcome() -> None:
    recorder = Recorder()
    recorder.dispatch("a1", ("abandon", None))
    assert verdicts(recorder)["boundary:dispatch"] == "passed"


def test_success_without_a_captured_attempt_is_violated_when_git_covers_the_ree() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="missing")
    recorder.attempt("other")
    assert findings(recorder, "run-success-is-backed") == ["violated: Attempt missing was never recorded"]


def test_success_without_git_evidence_for_the_ree_is_inconclusive() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="missing")
    assert findings(recorder, "run-success-is-backed", journal(), git("another-ree")) == [
        "inconclusive: no git evidence from core covers ree-1"
    ]


def test_success_backed_by_a_failed_attempt_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1", outcome="failed")
    assert findings(recorder, "run-success-is-backed") == [
        "violated: Attempt a1 reached captured with {'outcome': 'failed'}"
    ]


def test_a_success_without_an_attempt_id_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded")
    assert findings(recorder, "run-success-is-backed") == ["violated: has no attempt_id"]


def test_provisioning_runs_need_no_attempt() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "provisioning", "succeeded", operation="provision")
    assert verdicts(recorder)["run-success-is-backed"] == "not_triggered"


def test_an_attempt_still_executing_is_inconclusive() -> None:
    recorder = Recorder()
    recorder.dispatch("a1", ("receive", "result"))
    recorder.attempt("a1", captured=False)
    assert findings(recorder, "dispatch-success-is-captured") == ["inconclusive: Attempt a1 is still completed"]


def test_an_attempt_without_a_dispatch_is_violated() -> None:
    recorder = Recorder()
    recorder.attempt("a1")
    assert findings(recorder, "execution-was-dispatched") == ["violated: no dispatch.exec_action a1"]


def assigned_allocation(recorder: Recorder) -> None:
    for current, target in [
        (None, "requested"),
        ("requested", "waiting_for_workbench"),
        ("waiting_for_workbench", "ready"),
        ("ready", "assigned"),
    ]:
        recorder._add(
            "api-000001",
            kind="transition",
            owner="supervisor",
            subject="Allocation",
            key="alloc-1",
            source_state=current,
            target_state=target,
            facts={},
        )


def final(source: Source) -> Source:
    return source.model_copy(update={"final": True})


def test_an_allocation_left_assigned_at_a_final_close_is_violated() -> None:
    recorder = Recorder()
    assigned_allocation(recorder)
    expected = "violated: still assigned when api-000001 closed for good"
    assert findings(recorder, "allocation-ends", final(journal()), git(REE)) == [expected]
    assert findings(recorder, "machine:Allocation", final(journal()), git(REE)) == [expected]


def test_an_allocation_outlives_an_ordinary_close_or_an_open_journal() -> None:
    recorder = Recorder()
    assigned_allocation(recorder)
    for source in (journal(), journal(closed=False), final(journal(closed=False))):
        assert verdicts(recorder, source, git(REE))["allocation-ends"] == "inconclusive"
        assert verdicts(recorder, source, git(REE))["machine:Allocation"] == "passed"


def test_a_released_allocation_passes_at_a_final_close() -> None:
    recorder = Recorder()
    assigned_allocation(recorder)
    for current, target in [("assigned", "draining"), ("draining", "released")]:
        recorder._add(
            "api-000001",
            kind="transition",
            owner="supervisor",
            subject="Allocation",
            key="alloc-1",
            source_state=current,
            target_state=target,
            facts={},
        )
    found = verdicts(recorder, final(journal()), git(REE))
    assert (found["allocation-ends"], found["machine:Allocation"]) == ("passed", "passed")


def test_an_assigned_allocation_that_never_ends_is_inconclusive() -> None:
    recorder = Recorder()
    for current, target in [
        (None, "requested"),
        ("requested", "waiting_for_workbench"),
        ("waiting_for_workbench", "ready"),
        ("ready", "assigned"),
    ]:
        recorder._add(
            "api-000001",
            kind="transition",
            owner="supervisor",
            subject="Allocation",
            key="alloc-1",
            source_state=current,
            target_state=target,
            facts={},
        )
    assert findings(recorder, "allocation-ends") == ["inconclusive: still assigned"]


def test_journals_written_against_another_specification_are_inconclusive() -> None:
    recorder = Recorder()
    complete_command(recorder)
    result = verdicts(recorder, journal(digest="sha256:old"), git(REE))
    assert result["evidence"] == "inconclusive"


def test_events_for_undeclared_subjects_are_violated() -> None:
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
    assert verdicts(recorder)["evidence"] == "violated"


def judgements(recorder: Recorder) -> list[tuple[str, str, str]]:
    model, _, _ = replay(SPEC, Evidence(sources=(journal(), git(REE)), events=tuple(recorder.events)))
    return [(j.rule, j.event, j.verdict) for j in judge_occurrences(model)]


def test_each_occurrence_is_judged_at_the_event_that_triggered_it() -> None:
    recorder = Recorder()
    complete_command(recorder)
    found = judgements(recorder)
    settled = next(e for e in recorder.events if e.subject == "Run" and e.target_state == "succeeded")
    assert ("run-success-is-backed", settled.ref, "passed") in found
    model, _, _ = replay(SPEC, Evidence(sources=(journal(), git(REE)), events=tuple(recorder.events)))
    captured = next(j for j in judge_occurrences(model) if j.rule == "execution-was-dispatched")
    assert (captured.subject, captured.key) == ("Attempt", "a1")
    assert {verdict for _, _, verdict in found} == {"passed"}


def test_occurrence_verdicts_agree_with_the_rule_verdicts() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1", outcome="failed")
    rules = verdicts(recorder)
    for rule, _, verdict in judgements(recorder):
        assert verdict == rules[rule] or (verdict == "passed" and rules[rule] != "not_triggered")
    assert ("run-success-is-backed", "api-000001#3", "violated") in judgements(recorder)


# ---- Snapshots taken while the system ran ---------------------------------------


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
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="missing")  # api-000001#1..3
    recorder.attempt("other")
    sources = (journal(closed=False), git(REE, cut={"api-000001": cut}))
    assert findings(recorder, "run-success-is-backed", *sources) == [expected]


def test_a_snapshot_cannot_vouch_for_a_journal_it_was_not_cut_against() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="missing")
    recorder.attempt("other")
    sources = (journal(closed=False), git(REE, cut={"workbench-000001": (5, 6)}))
    assert findings(recorder, "run-success-is-backed", *sources) == [
        "inconclusive: the evidence cannot place api-000001#3 against when git:ree was taken"
    ]


def observed(recorder: Recorder, state: str) -> None:
    recorder.events.append(
        Event(
            source="stores",
            position=1,
            kind="observed",
            owner="api",
            subject="Run",
            key="run-1",
            partition=REE,
            target_state=state,
        )
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("running", []),  # The state when the cut began.
        ("succeeded", []),  # Written to the store just before the snapshot, journaled just after the cut.
        ("queued", ["violated: persisted as queued, but around stores the journal shows ['running', 'succeeded']"]),
    ],
)
def test_a_live_store_snapshot_holds_a_state_reached_around_its_cut(state: str, expected: list[str]) -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="a1")  # api-000001#1..3
    recorder.attempt("a1")
    observed(recorder, state)
    sources = (journal(closed=False), git(REE), stores(cut={"api-000001": (2, 2)}))
    assert findings(recorder, "reconciliation", *sources) == expected


def test_a_store_snapshot_after_the_owners_stopped_must_match_exactly() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running", "succeeded", attempt_id="a1")
    recorder.attempt("a1")
    observed(recorder, "running")
    assert findings(recorder, "reconciliation", journal(), git(REE), stores()) == [
        "violated: persisted as running, but the journal replays to succeeded"
    ]


# ---- Order across sources, evidenced by citations ----------------------------------


def test_without_citations_the_order_across_sources_is_unknown() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running")
    recorder.dispatch("a1", ("receive", "result"), commit=None)
    recorder.attempt("a1")  # Names no request, and the result names no commit.
    recorder.settle("run-1", "running", "succeeded", "a1")
    result = verdicts(recorder)
    assert result["execution-was-dispatched"] == "inconclusive"
    assert result["dispatch-success-is-captured"] == "inconclusive"
    assert result["run-success-is-backed"] == "inconclusive"
    assert findings(recorder, "execution-was-dispatched") == [
        "inconclusive: the evidence cannot order dispatch.exec_action a1 against it"
    ]


def test_a_citation_of_a_record_the_evidence_does_not_hold_is_violated() -> None:
    recorder = Recorder()
    recorder.run("run-1", "queued", "running")
    recorder.dispatch("a1", ("receive", "result"), commit="d" * 40)  # Not the commit that captured a1.
    recorder.attempt("a1", dispatched_by="api-000001#99")  # Not the request that sent it.
    recorder.settle("run-1", "running", "succeeded", "a1")
    assert sorted(findings(recorder, "boundary:dispatch")) == [
        "violated: names api-000001#99, but the evidence records ['api-000001#3']",
        f"violated: names {'d' * 40}, but the evidence records ['{'c' * 40}']",
    ]
