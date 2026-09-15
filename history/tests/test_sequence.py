import json

import pytest
from history.tests.fixtures import make_execution

from repo2ree_history import SystemExecution
from repo2ree_history.core.sequence import render_sequence
from repo2ree_history.shell.execution import load_execution


def test_collection_order_does_not_change_diagram():
    execution = make_execution()
    data = execution.model_dump(mode="json")
    data["events"].reverse()
    assert render_sequence(execution) == render_sequence(SystemExecution.model_validate(data))
    assert "synthetic" in render_sequence(execution)
    assert "event-2 supports event-3" in render_sequence(execution)


def test_cross_process_causality_and_process_epochs():
    data = make_execution().model_dump(mode="json")
    last = data["events"][-1]
    last["producer"] = {"component": "supervisor", "instance_id": "server", "epoch": "restart-1"}
    last["sequence"] = 1
    last["causes"] = ["event-6"]
    data["recording"]["producers"][0]["last_sequence"] = 6
    diagram = render_sequence(SystemExecution.model_validate(data))
    assert "supervisor/server/restart-1" in diagram
    assert "workbench/bench-process/boot-1" in diagram
    assert "event-6 supports event-7" in diagram
    assert "capture_extent_unknown" in diagram


def test_partial_trace_labels_missing_evidence_without_inventing_lane():
    data = make_execution().model_dump(mode="json")
    data["events"].pop(1)
    diagram = render_sequence(SystemExecution.model_validate(data))
    assert "INCOMPLETE" in diagram
    assert "missing_authentication" in diagram
    assert "event-2 supports event-3" not in diagram


def test_cycle_refused():
    data = make_execution().model_dump(mode="json")
    data["events"][0]["causes"] = ["event-7"]
    with pytest.raises(ValueError, match="causal_cycle"):
        render_sequence(SystemExecution.model_validate(data))


def test_diagram_text_cannot_inject_mermaid():
    data = make_execution().model_dump(mode="json")
    data["execution_id"] = "evil\nparticipant injected<script>"
    for event in data["events"]:
        event["execution_id"] = data["execution_id"]
    diagram = render_sequence(SystemExecution.model_validate(data))
    assert "\nparticipant injected" not in diagram
    assert "<script>" not in diagram


def test_split_and_single_formats_match(tmp_path):
    data = make_execution().model_dump(mode="json")
    path = tmp_path / "execution.json"
    path.write_text(json.dumps(data))
    expected = load_execution(path)
    events = data.pop("events")
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    (tmp_path / "events.ndjson").write_text("\n".join(json.dumps(event) for event in events))
    assert load_execution(tmp_path) == expected


def test_test_manifest_is_not_silently_treated_as_master_trace(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text('{"nodeid":"test-example", "outcome":"passed"}')
    with pytest.raises(ValueError, match="not master traces"):
        load_execution(path)
