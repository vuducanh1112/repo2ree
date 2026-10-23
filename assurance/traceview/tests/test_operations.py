"""A dossier becomes operations, authoring between them, and each operation's path across components."""

from __future__ import annotations

from traceview_scenario import REE, Scenario, build_spans, provision_spans, recorded, trace_of


def test_the_scenario_conforms() -> None:
    assert trace_of(recorded()).verdict == "passed"


def test_operations_are_attempts_with_a_run_and_authoring_is_collapsed_between_them() -> None:
    trace = trace_of(recorded())
    assert [(entry.kind, entry.name) for entry in trace.entries] == [
        ("setup", "provision"),
        ("operation", "build_runtime"),
        ("authoring", "authoring"),
        ("operation", "generate_sbom"),
        ("setup", "release"),
    ]
    authoring = trace.entries[2]
    assert (authoring.operations, authoring.attempts, authoring.failed) == ({"patch_ree_definition": 1}, 1, 0)
    assert [(c.step, c.before, c.after) for c in trace.entries[1].changes] == [("runtime", "missing", "current")]


def test_standings_trace_the_step_states_column_by_column() -> None:
    standings = trace_of(recorded()).standings
    assert [s.label for s in standings] == ["created", "build_runtime", "authoring", "generate_sbom"]
    assert standings[0].states == {"runtime": "missing", "sbom": "missing"}
    # The authoring column shows what authoring did, and nothing of the operation that followed it.
    assert standings[2].states == {"runtime": "current", "sbom": "missing", "test_activation": "missing"}
    assert standings[2].changed == ("test_activation",)
    assert standings[3].states["sbom"] == "current"


def test_rules_attach_to_the_entries_whose_events_triggered_them() -> None:
    build = trace_of(recorded()).entries[1]
    assert {(hit.rule, hit.verdict) for hit in build.rules} >= {
        ("api-success-is-recorded", "passed"),
        ("dispatch-success-is-captured", "passed"),
    }


def test_spans_annotate_but_never_change_what_was_checked() -> None:
    plain, annotated = trace_of(recorded()), trace_of(recorded(), build_spans())
    assert annotated.verdict == plain.verdict
    for left, right in zip(plain.entries, annotated.entries, strict=True):
        assert (left.name, left.rules, left.changes) == (right.name, right.rules, right.changes)
    # The longest spans of the operation's traces, in start order; the 60 ms request is not among them.
    assert [s.name for s in annotated.entries[1].spans] == [
        "run.build",
        "workbench.dispatch_action",
        "workbench.request",
        "executor.build_runtime",
        "command.build_runtime",
        "process.exec",
    ]


def test_a_sequence_follows_one_operation_across_components() -> None:
    sequence = trace_of(recorded(), build_spans()).entries[1].sequence
    assert sequence is not None
    assert [lane.id for lane in sequence.lanes] == ["client", "api", "supervisor", "workbench", "executor", "core"]
    lines = [(row.provenance, row.lane, row.to, row.label) for row in sequence.rows]
    assert lines[0] == ("span", "client", "api", "POST /rees/{id}/build-runtime")
    assert ("journal", "supervisor", "workbench", "exec_action · build_runtime") in lines
    assert ("journal", "workbench", "supervisor", "result · succeeded") in lines
    assert ("git", "core", None, "commit c2000000") in lines
    assert any(row.tone == "gap" and row.label == "350 ms without spans" for row in sequence.rows)


def test_attempt_states_are_placed_inside_the_command_span_and_marked_inferred() -> None:
    sequence = trace_of(recorded(), build_spans()).entries[1].sequence
    assert sequence is not None
    command = next(a for a in sequence.activations if a.lane == "core")
    attempt = [row for row in sequence.rows if row.label.startswith("Attempt")]
    assert [row.label for row in attempt] == [
        f"Attempt → {s}" for s in ("pending", "executing", "completed", "captured")
    ]
    assert all(row.provenance == "inferred" and command.start <= row.t <= command.end for row in attempt)
    process = next(row for row in sequence.rows if row.label == "$ sh build.sh")
    assert attempt[1].t < process.t < attempt[2].t


def test_without_spans_the_attempt_sits_inside_its_dispatch_bracket() -> None:
    sequence = trace_of(recorded()).entries[1].sequence
    assert sequence is not None
    assert {row.provenance for row in sequence.rows} == {"journal", "inferred", "git"}
    sent = next(row.t for row in sequence.rows if row.label.startswith("exec_action"))
    answered = next(row.t for row in sequence.rows if row.label.startswith("result"))
    inside = [row for row in sequence.rows if row.provenance in ("inferred", "git")]
    assert all(sent < row.t < answered for row in inside)


def two_rees() -> Scenario:
    """ree-1's dossier, with ree-2 provisioned and built in the same API journal and its own Git history.

    Both histories number capture commits from the same blocks, so their positions collide; only the
    journal can say what happened in which order.
    """
    s = recorded()
    s.ree, s.git, s.alloc = "ree-2", "git:ree-2", "alloc-2"
    s.provision("run-provision-2", 70.0)
    s.operation("run-build-2", "build_runtime", "b-build", "build_runtime", 80.0)
    s.commit(1, None, "initialize_ree", "", [], (None, "draft"))
    s.commit(
        2,
        "b-build",
        "build_runtime",
        "run-build-2",
        [("runtime", None, "missing", "baseline"), ("runtime", "missing", "current", "operation")],
        ("draft", "draft"),
    )
    return s


def test_each_ree_gets_only_its_own_operations() -> None:
    scenario = two_rees()
    first, second = trace_of(scenario, ree=REE), trace_of(scenario, ree="ree-2")
    assert [entry.name for entry in first.entries] == [entry.name for entry in trace_of(recorded()).entries]
    assert [(entry.kind, entry.name) for entry in second.entries] == [
        ("setup", "provision"),
        ("operation", "build_runtime"),
    ]
    assert second.standings[-1].states == {"runtime": "current"}
    assert second.entries[1].run is not None
    assert second.entries[1].run.key == "act-run-build-2"


def test_review_histories_are_counted_not_drawn() -> None:
    s = recorded()
    s.git = "git:ree/reviews/r1"
    s.dispatch("r-acquire", "review_acquire_source", "review-1", 30.0, 30.5)
    s.commit(2, "r-acquire", "review_acquire_source", "review-1", [], None)
    trace = trace_of(s)
    assert trace.reviews == 1
    assert "review_acquire_source" not in {entry.name for entry in trace.entries}
    assert [entry.name for entry in trace.entries] == [entry.name for entry in trace_of(recorded()).entries]


def test_setup_is_placed_by_the_journal_between_the_operations_it_came_between() -> None:
    s = Scenario()
    s.provision("run-provision", 0.0)
    s.operation("run-build", "build", "a-build", "build_runtime", 10.0)
    # The workbench is lost; the API provisions a new one before the SBOM run.
    s.allocation([(15.0, "lost")], start="assigned")
    s.alloc = "alloc-2"
    s.provision("run-reprovision", 16.0)
    s.operation("run-sbom", "sbom", "a-sbom", "generate_sbom", 25.0)
    s.commit(1, None, "initialize_ree", "", [], (None, "draft"))
    s.commit(
        2,
        "a-build",
        "build_runtime",
        "run-build",
        [("runtime", None, "missing", "baseline"), ("runtime", "missing", "current", "operation")],
        ("draft", "draft"),
    )
    s.commit(3, "a-sbom", "generate_sbom", "run-sbom", [("sbom", None, "current", "operation")], ("draft", "draft"))
    entries = [(entry.name, entry.outcome) for entry in trace_of(s).entries]
    assert entries == [
        ("provision", "succeeded"),
        ("build_runtime", "succeeded"),
        ("release", "lost"),
        ("provision", "succeeded"),
        ("generate_sbom", "succeeded"),
    ]


def test_provisioning_follows_the_supervisor_into_the_provider_by_trace() -> None:
    sequence = trace_of(recorded(), provision_spans()).entries[0].sequence
    assert sequence is not None
    assert "provider" in [lane.id for lane in sequence.lanes]
    lines = [(row.provenance, row.lane, row.to, row.label) for row in sequence.rows]
    assert ("span", "supervisor", "provider", "ensure_allocation") in lines
    assert ("span", "provider", None, "docker pull") in lines
    assert ("journal", "supervisor", None, "Allocation → assigned") in lines
    assert all(row.provenance != "time" for row in sequence.rows)
