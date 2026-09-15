import json
from pathlib import Path

import pytest
from history.tests.fixtures import make_execution
from pydantic import ValidationError

from repo2ree_history import (
    Boundary,
    FileEntry,
    HistoryEvent,
    LayoutObserved,
    SystemExecution,
    validate_execution,
)
from repo2ree_history.core.evidence import AssemblyResult


def document():
    return make_execution().model_dump(mode="json")


def codes(data):
    return {issue.code for issue in validate_execution(SystemExecution.model_validate(data))}


def test_execution_round_trip_and_schema():
    execution = make_execution()
    assert SystemExecution.model_validate_json(execution.model_dump_json()) == execution
    assert validate_execution(execution) == ()
    assert (
        json.loads(Path("history/schema/system-execution.schema.json").read_text())
        == SystemExecution.model_json_schema()
    )


def test_collection_order_and_clock_skew_do_not_define_causality():
    data = document()
    data["events"].reverse()
    data["events"][0]["observed_at"] = "2020-01-01T00:00:00Z"
    assert codes(data) == set()


@pytest.mark.parametrize(
    "mutation", ["foreign_execution", "duplicate_event", "duplicate_artifact", "untyped_payload", "missing_operation"]
)
def test_invalid_execution_shape(mutation):
    data = document()
    if mutation == "foreign_execution":
        data["events"][0]["execution_id"] = "other"
    elif mutation == "duplicate_event":
        data["events"].append(data["events"][0])
    elif mutation == "duplicate_artifact":
        data["artifacts"].append(data["artifacts"][0])
    elif mutation == "untyped_payload":
        data["events"][0]["payload"] = {"kind": "anything", "data": {}}
    else:
        data["events"][3]["operation"] = None
    with pytest.raises(ValidationError):
        SystemExecution.model_validate(data)


def test_partial_recording_remains_parseable_and_reports_missing_evidence():
    data = document()
    data["events"] = [data["events"][2]]
    data["events"][0]["causes"] = ["lost-event"]
    data["recording"]["status"] = "interrupted"
    assert codes(data) >= {
        "missing_cause",
        "missing_authentication",
        "capture_gap",
        "missing_execution_start",
        "missing_execution_end",
    }
    assert all(issue.severity == "incomplete" for issue in validate_execution(SystemExecution.model_validate(data)))


def test_causal_cycle_including_local_sequence_is_invalid():
    data = document()
    data["events"][0]["causes"] = ["event-7"]
    assert "causal_cycle" in codes(data)


def test_duplicate_sequence_and_missing_sequence_are_reported():
    data = document()
    data["events"][4]["sequence"] = 4
    assert codes(data) >= {"duplicate_sequence", "sequence_gap", "capture_gap"}


@pytest.mark.parametrize(("field", "value"), [("session_id", "other"), ("request_id", "other")])
def test_authentication_must_match_interaction(field, value):
    data = document()
    data["events"][1]["payload"][field] = value
    assert "authentication_binding" in codes(data)


def test_rejected_authentication_is_valid_evidence_for_a_contract_violation():
    data = document()
    data["events"][1]["payload"]["outcome"] = "rejected"
    assert codes(data) == set()  # Structural validity must not reject observed bad behavior.


def test_unknown_delivery_does_not_become_complete_when_recording_closes():
    data = document()
    data["recording"]["producers"][0]["delivery"] = "unknown"
    assert "delivery_unconfirmed" in codes(data)


def test_git_repository_reference_and_test_attribution_are_checked():
    data = document()
    data["artifacts"] = []
    data["tests"][0]["event_ids"] = ["missing"]
    data["events"][0]["artifact_ids"] = ["missing-file"]
    assert codes(data) >= {"missing_repository", "missing_test_event", "missing_artifact"}


def test_boundary_preserves_failed_operation_readiness_without_asserting_it():
    boundary = Boundary(
        event="operation_finished",
        status="failed",
        scope="author",
        mutates_ree=True,
        root_expected=True,
        writers_stopped=False,
        capture_prepared=False,
        locks_held=False,
        history_published=False,
        capture_format="repository_v2",
    )
    observation = LayoutObserved(
        boundary=boundary, entries=(FileEntry(path="ree.json", kind="missing"),), coverage="managed_paths"
    )
    assert not observation.boundary.locks_held
    assert observation.entries[0].kind == "missing"
    with pytest.raises(ValidationError, match="duplicate layout path"):
        LayoutObserved(boundary=boundary, entries=observation.entries * 2, coverage="managed_paths")


@pytest.mark.parametrize("path", ["/ree.json", "../ree.json", "foo/../ree.json", "foo\\ree.json"])
def test_layout_paths_are_portable_and_relative(path):
    with pytest.raises(ValidationError):
        FileEntry(path=path, kind="file")


def test_operation_context_and_git_metadata_match_existing_wire_shapes():
    # Fixtures mirror ExecutionContext / HistoryReference without importing protocol.
    # Protocol adapters will own the actual conversion and compatibility tests.
    event = document()["events"][5]
    event["operation"] = {
        "operation_id": "logical-op",
        "attempt_id": "retry-2",
        "operation": "seal",
        "run_id": "background-run",
    }
    event["payload"].update(
        before_snapshot_id="a" * 40, after_snapshot_id="b" * 40, capture_status="captured", changed=True
    )
    parsed = HistoryEvent.model_validate(event)
    assert parsed.operation is not None
    assert parsed.operation.attempt_id != parsed.operation.run_id


def test_recording_end_is_distinct_from_success_and_shutdown():
    data = document()
    data["events"][-1]["payload"]["reason"] = "observation_stopped"
    assert codes(data) == set()
    data["recording"]["finished_at"] = None
    with pytest.raises(ValidationError):
        SystemExecution.model_validate(data)


def test_reconnections_keep_lifecycle_but_replacement_requires_new_execution():
    data = document()
    data["events"][-1]["resources"]["session_id"] = "reconnected-session"
    assert codes(data) == set()
    data["events"][-1]["resources"]["workbench_instance_id"] = "replacement"
    assert "multiple_workbench_lifecycles" in codes(data)


def test_attempt_cannot_change_logical_operation_between_components():
    data = document()
    data["events"][4]["operation"]["operation_id"] = "other-operation"
    assert "attempt_identity_conflict" in codes(data)


def test_assembly_schema_matches_export():
    assert json.loads(Path("history/schema/assembly.schema.json").read_text()) == AssemblyResult.model_json_schema()
