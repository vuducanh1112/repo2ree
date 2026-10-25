"""Many traces fold into one catalogue: each operation once, its lines counted across the instances that ran it."""

from __future__ import annotations

from pathlib import Path

import pytest
from traceview_scenario import build_spans, recorded, trace_of

from repo2ree_assurance_traceview.catalogue import OperationCatalogue, Undrawn, build_catalogue, mask
from repo2ree_assurance_traceview.cli import main
from repo2ree_assurance_traceview.model import Entry, Row


def test_operations_come_once_each_in_the_order_they_usually_take() -> None:
    catalogue = build_catalogue([("a", trace_of(recorded(), build_spans())), ("b", trace_of(recorded()))])
    assert [(op.kind, op.name) for op in catalogue.operations] == [
        ("setup", "provision"),
        ("operation", "build_runtime"),
        ("operation", "generate_sbom"),
        ("setup", "release"),
    ]
    build = catalogue.operations[1]
    assert [(i.source, i.outcome) for i in build.instances] == [("a", "succeeded"), ("b", "succeeded")]


def test_a_failure_path_is_drawn_apart_from_the_success_it_diverges_from() -> None:
    trace = trace_of(recorded())
    entries = tuple(
        entry.model_copy(update={"outcome": "failed"}) if entry.name == "build_runtime" else entry
        for entry in trace.entries
    )
    failed = trace.model_copy(update={"entries": entries})
    catalogue = build_catalogue([("a", trace), ("b", trace), ("c", failed)])
    builds = [
        (op.outcome, [i.source for i in op.instances]) for op in catalogue.operations if op.name == "build_runtime"
    ]
    assert builds == [("succeeded", ["a", "b"]), ("failed", ["c"])]


def test_each_line_counts_the_instances_that_show_it() -> None:
    build = build_catalogue([("a", trace_of(recorded(), build_spans())), ("b", trace_of(recorded()))]).operations[1]
    everything = {(line.provenance, line.label): line.seen for line in (*build.lines, *build.elsewhere)}
    # Both instances journal the dispatch and capture it in Git; only one recorded spans.
    assert everything[("journal", "exec_action · build_runtime")] == 2
    assert everything[("git", "commit …")] == 2
    assert everything[("span", "POST /rees/{id}/build-runtime")] == 1
    assert all(line.seen < 2 for line in build.elsewhere)


def test_requests_matched_only_by_time_are_not_part_of_the_operation() -> None:
    trace = trace_of(recorded(), build_spans())
    earlier = Row(t=0.0, lane="client", to="api", label="PUT /rees/{id}/files/content", provenance="time")

    def with_earlier(entry: Entry) -> Entry:
        if entry.name != "build_runtime" or entry.sequence is None:
            return entry
        rows = (earlier, *entry.sequence.rows)
        return entry.model_copy(update={"sequence": entry.sequence.model_copy(update={"rows": rows})})

    padded = trace.model_copy(update={"entries": tuple(with_earlier(entry) for entry in trace.entries)})
    build = build_catalogue([("a", padded)]).operations[1]
    assert build.lines == build_catalogue([("a", trace)]).operations[1].lines
    assert build.lines[0].t == 0.0  # Time runs from the operation's own first line.


def test_a_lane_is_reached_only_as_far_as_every_instance_reaches_it() -> None:
    with_spans = build_catalogue([("a", trace_of(recorded(), build_spans()))]).operations[1].reach
    assert (with_spans["api"], with_spans["core"]) == ("checked", "checked")
    # The supervisor's journal holds what it sent and was answered, nothing the workbench recorded itself.
    assert with_spans["workbench"] == "exchanged"
    assert with_spans["executor"] == "span"

    both = build_catalogue([("a", trace_of(recorded(), build_spans())), ("b", trace_of(recorded()))])
    assert both.operations[1].reach["executor"] == "none"


def test_rules_are_tallied_by_verdict_over_every_instance() -> None:
    build = build_catalogue([("a", trace_of(recorded())), ("b", trace_of(recorded()))]).operations[1]
    tally = {t.rule: (t.passed, t.violated, t.inconclusive) for t in build.rules}
    assert tally["api-success-is-recorded"] == (2, 0, 0)


def test_what_cannot_be_drawn_is_listed_with_its_reason() -> None:
    undrawn = Undrawn(source="v", test="t", verdict="violated", reason="no REE history in this dossier")
    catalogue = build_catalogue([], [undrawn])
    assert (catalogue.operations, catalogue.undrawn) == ((), (undrawn,))


@pytest.mark.parametrize(
    ("label", "shape"),
    [
        ("commit c2000000", "commit …"),
        ("350 ms without spans", "… without spans"),
        ("3x · 0.54 s · 1 failed", "… · … · 1 failed"),
        ("exec_action · build_runtime", "exec_action · build_runtime"),
    ],
)
def test_labels_are_alike_once_ids_durations_and_counts_are_masked(label: str, shape: str) -> None:
    assert mask(label) == shape


def test_the_command_line_lists_a_verification_it_cannot_read(tmp_path: Path) -> None:
    output = tmp_path / "operations.json"
    assert main(["operations", str(tmp_path / "absent"), "-o", str(output)]) == 0
    catalogue = OperationCatalogue.model_validate_json(output.read_text())
    assert catalogue.operations == ()
    assert [u.source for u in catalogue.undrawn] == [str(tmp_path / "absent")]
    assert "not a verification" in catalogue.undrawn[0].reason
