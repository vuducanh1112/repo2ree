"""The lifecycle: every entry and every action no entry draws, as one sequence in journal order."""

from __future__ import annotations

from typing import Any

from traceview_scenario import REE, Scenario, build_spans, dossier_of, recorded, trace_of

from repo2ree_assurance_traceview.model import AuthoringFold, JournalMark, Lifecycle, SessionMove


def requested(s: Scenario, t: float, key: str, action: str, state: str, **facts: Any) -> None:
    """A short author action without a run: requested, then answered ``state``."""
    for previous, target in ((None, "requested"), ("requested", state)):
        s.journal(
            t,
            kind="transition",
            owner="api",
            subject="AuthorApiAction",
            key=key,
            source_state=previous,
            target_state=target,
            facts={"action": action, **facts},
        )


def lost(s: Scenario) -> Scenario:
    """A build whose workbench was lost: its dispatch went unanswered, and the run failed naming no attempt."""
    s.run("run-lost", [(30.0, "requested"), (30.1, "running")], action="build_runtime")
    s.journal(
        30.2,
        kind="send",
        owner="supervisor",
        subject="start_run",
        key="a-lost",
        message="start_run",
        facts={"operation": "build_runtime", "run_id": "run-lost", "session": "session-1"},
    )
    s.requests["a-lost"] = f"api-000001#{s.seq}"
    s.journal(70.0, kind="receive", owner="supervisor", subject="start_run", key="a-lost", message="unavailable")
    s.action(70.1, "run-lost", "running", "failed", action="build_runtime", failure_category="internal")
    s.commit(5, "a-lost", "build_runtime", "run-lost", [], ("draft", "draft"))
    return s


def test_the_lifecycle_joins_every_entry_in_journal_order() -> None:
    trace = trace_of(recorded(), build_spans())
    lifecycle = trace.lifecycle
    assert lifecycle is not None
    assert [(segment.kind, segment.label, segment.entry) for segment in lifecycle.segments] == [
        ("setup", "provision", 0),
        ("authoring", "authoring", 1),
        ("operation", "build_runtime", 2),
        ("operation", "generate_sbom", 3),
    ]
    # Segments follow one another, and each draws its own entry's lines.
    assert lifecycle.segments[0].first == 0
    for before, after in zip(lifecycle.segments, lifecycle.segments[1:], strict=False):
        assert after.first == before.last + 1
    build = lifecycle.segments[2]
    own = trace.entries[2].sequence
    assert own is not None
    drawn = lifecycle.rows[build.first : build.last + 1]
    assert drawn == tuple(row for row in own.rows if row.provenance != "time")


def test_authoring_is_one_folded_line() -> None:
    lifecycle = trace_of(recorded()).lifecycle
    assert lifecycle is not None
    authoring = lifecycle.segments[1]
    (line,) = lifecycle.rows[authoring.first : authoring.last + 1]
    assert (line.tone, line.label) == ("fold", "")
    assert line.said == AuthoringFold(attempts=1, failed=0, operations={"patch_ree_definition": 1})


def test_a_run_lost_with_its_workbench_is_an_operation_through_its_dispatch() -> None:
    trace = trace_of(lost(recorded()))
    build = trace.entries[-1]
    assert (build.kind, build.name, build.dispatch and build.dispatch.outcome) == (
        "operation",
        "build_runtime",
        "unavailable",
    )
    assert build.run is not None
    assert [state.state for state in build.run.states] == ["requested", "running", "failed"]
    lifecycle = trace.lifecycle
    assert lifecycle is not None
    assert [segment.label for segment in lifecycle.segments if segment.kind == "action"] == []


def test_actions_no_entry_draws_are_placed_by_journal_position_and_reads_are_left_out() -> None:
    s = recorded()
    requested(s, 25.0, "act-write", "write_file", "failed", path="notes.txt", http_status=503)
    requested(s, 26.0, "act-view", "view_action", "succeeded", about_action_id="act-run-build")
    s.operation("run-test", "test_activation", "a-test", "test_activation", 30.0)
    s.commit(5, "a-test", "test_activation", "run-test", [], ("draft", "draft"))
    requested(s, 60.0, "act-delete", "delete_ree", "succeeded", store_id="lab-1")
    lifecycle = trace_of(s).lifecycle
    assert lifecycle is not None
    assert [(segment.kind, segment.label, segment.outcome) for segment in lifecycle.segments] == [
        ("setup", "provision", "succeeded"),
        ("authoring", "authoring", None),
        ("operation", "build_runtime", "succeeded"),
        ("operation", "generate_sbom", "succeeded"),
        ("action", "write_file", "failed"),
        ("operation", "test_activation", "succeeded"),
        ("action", "delete_ree", "succeeded"),
    ]
    assert not any("view_action" in row.label for row in lifecycle.rows)


def test_lines_matched_by_time_are_left_to_the_operation_they_belong_to() -> None:
    trace = trace_of(recorded(), build_spans())
    lifecycle = trace.lifecycle
    assert lifecycle is not None
    assert all(row.provenance != "time" for row in lifecycle.rows)
    assert all(activity.provenance != "time" for activity in lifecycle.activations)


def test_a_run_whose_attempt_was_never_captured_still_shows_its_dispatch() -> None:
    s = recorded()
    s.run("run-killed", [(30.0, "requested"), (30.1, "running")], action="build_runtime")
    s.journal(
        30.2,
        kind="send",
        owner="supervisor",
        subject="start_run",
        key="a-killed",
        message="start_run",
        facts={"operation": "build_runtime", "run_id": "run-killed", "session": "session-1"},
    )
    s.journal(50.0, kind="receive", owner="supervisor", subject="start_run", key="a-killed", message="unavailable")
    s.action(50.1, "run-killed", "running", "failed", action="build_runtime", failure_category="internal")
    lifecycle = trace_of(s).lifecycle
    assert lifecycle is not None
    killed = lifecycle.segments[-1]
    assert (killed.kind, killed.label, killed.outcome) == ("action", "build_runtime", "failed")
    labels = [row.label for row in lifecycle.rows[killed.first : killed.last + 1]]
    assert labels == [
        "build_runtime → requested",
        "build_runtime → running",
        "start_run · build_runtime",
        "unavailable",
        "build_runtime → failed",
    ]


def served(s: Scenario, t: float, key: str, *, store: str = "lab-1", nonce: str = "n-1") -> None:
    """A workbench admitted to ``store``."""
    s.session(t, key, None, "opened", store=store, nonce=nonce)
    s.session(t, key, "opened", "connected", store=store, nonce=nonce, backend="host", slots=1)


def said(lifecycle: Lifecycle, kind: str) -> list[object]:
    """What the lines of the lifecycle's ``kind`` stretches carry, for the page to phrase."""
    return [
        row.said
        for segment in lifecycle.segments
        if segment.kind == kind
        for row in lifecycle.rows[segment.first : segment.last + 1]
    ]


def test_an_rees_lifecycle_draws_its_stores_sessions_while_it_lived() -> None:
    s = Scenario()
    served(s, 0.0, "s1")
    served(s, 0.0, "elsewhere", store="lab-2")
    recorded(scenario=s)
    requested(s, 60.0, "act-delete", "delete_ree", "succeeded", store_id="lab-1")
    s.session(61.0, "s1", "connected", "lost", reason="closed", close_code=1006)
    lifecycle = trace_of(s).lifecycle
    assert lifecycle is not None
    assert (lifecycle.segments[0].kind, lifecycle.segments[0].label) == ("session", "lab-1")
    # The session serving the store when the REE was created; the end of it came after the REE's.
    assert said(lifecycle, "session") == [SessionMove(session="s1", state="connected", workbench="wb-1", nonce="n-1")]


def test_a_crashed_api_ends_its_journal_and_the_workbench_comes_back_as_a_new_session() -> None:
    s = Scenario()
    served(s, 0.0, "s1")
    recorded(scenario=s)
    s.restart()
    served(s, 40.0, "s2")
    requested(s, 60.0, "act-delete", "delete_ree", "succeeded", store_id="lab-1")
    lifecycle = trace_of(s).lifecycle
    assert lifecycle is not None
    assert said(lifecycle, "epoch") == [
        JournalMark(journal="api-000001", mark="crashed"),
        JournalMark(journal="api-000002", mark="opened"),
    ]
    assert said(lifecycle, "session")[-1] == SessionMove(
        session="s2", state="connected", workbench="wb-1", nonce="n-1", returning="s1"
    )
    kinds = [segment.kind for segment in lifecycle.segments]
    assert kinds.index("epoch") < len(kinds) - 1 - kinds[::-1].index("session") < kinds.index("action")


def test_the_dossier_draws_every_ree_and_every_stores_sessions() -> None:
    s = Scenario()
    served(s, 0.0, "s1")
    served(s, 0.0, "elsewhere", store="lab-2")
    recorded(scenario=s)
    whole = dossier_of(s)
    assert (whole.ree, whole.entries) == ("", ())
    lifecycle = whole.lifecycle
    assert lifecycle is not None
    assert {segment.ree for segment in lifecycle.segments if segment.kind not in ("session", "epoch")} == {REE}
    assert {segment.label for segment in lifecycle.segments if segment.kind == "session"} == {"lab-1", "lab-2"}


def test_a_dispatch_says_the_session_it_was_sent_on() -> None:
    lifecycle = trace_of(recorded()).lifecycle
    assert lifecycle is not None
    sent = [row for row in lifecycle.rows if row.label.startswith(("start_run", "follow_run"))]
    assert sent
    assert all(row.session == "session-1" for row in sent)
