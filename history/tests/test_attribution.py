"""REE membership must survive lifecycle changes without inventing ownership."""

import copy
import json

from history.tests.test_assembly import recording, span, state

from repo2ree_history.core.evidence import AssemblyResult
from repo2ree_history.core.validation import validate_execution
from repo2ree_history.shell.recording import assemble_recording


def operation(number, workbench, ree="ree", instance=None):
    value = span(number, workbench)
    value["context"]["trace_id"] = f"{number:032x}"
    value["attributes"].update(
        {
            "repo2ree.ree_id": ree,
            "repo2ree.operation_id": f"op-{number}",
            "repo2ree.attempt_id": f"attempt-{number}",
            "repo2ree.run_id": f"run-{number}",
        }
    )
    if instance:
        value["attributes"]["repo2ree.workbench_instance_id"] = instance
    return value


def test_resumed_ree_preserves_two_lifecycles_and_historical_receipts(tmp_path):
    current = state()
    current["state"]["workbench"]["workbench_id"] = "new"
    current["state"]["audit"] = {"old": {"receipt_run_id": "run-1"}, "new": {"receipt_run_id": "run-2"}}
    result = assemble_recording(recording(tmp_path, [operation(1, "old"), operation(2, "new")], [current]))
    assert len(result.executions) == 2
    (history,) = result.ree_histories
    assert len(history.event_ids) == 7
    assert len(history.execution_ids) == 2
    observed_state = next(event for event in result.events if event.payload.kind == "state.observed")
    old = next(event for event in result.events if event.resources.workbench_id == "old")
    assert old.execution_id != observed_state.execution_id
    assert not any(d.severity == "invalid" for d in result.diagnostics)
    assert not any(i.code == "missing_correlation" for e in result.executions for i in validate_execution(e))
    assert AssemblyResult.model_validate_json(result.model_dump_json()) == result


def test_same_workbench_id_with_new_instance_is_two_lifecycles(tmp_path):
    result = assemble_recording(
        recording(tmp_path, [operation(1, "wb", instance="first"), operation(2, "wb", instance="second")])
    )
    assert len(result.executions) == 2
    assert len(result.ree_histories) == 1
    assert not any(d.severity == "invalid" for d in result.diagnostics)


def test_shared_trace_does_not_merge_rees_or_workbenches(tmp_path):
    first, second = operation(1, "one", "ree-one"), operation(2, "two", "ree-two")
    second["context"]["trace_id"] = first["context"]["trace_id"]
    result = assemble_recording(recording(tmp_path, [first, second]))
    assert len(result.ree_histories) == len(result.executions) == 2
    assert all(len(history.event_ids) == 3 for history in result.ree_histories)


def test_provisioning_joins_only_through_explicit_allocation_association(tmp_path):
    provisioning = operation(1, None, None)
    provisioning["attributes"] = {"repo2ree.allocation_id": "allocation"}
    bound = operation(2, "wb")
    bound["attributes"]["repo2ree.allocation_id"] = "allocation"
    failed = copy.deepcopy(provisioning)
    failed["context"] = {"trace_id": "f" * 32, "span_id": "f" * 16}
    failed["attributes"]["repo2ree.allocation_id"] = "failed-allocation"
    result = assemble_recording(recording(tmp_path, [provisioning, bound, failed]))
    (history,) = result.ree_histories
    assert history.provisioning_event_ids == ("e00000",)
    assert result.events[0].resources.ree_id is None
    assert result.attributions[0].ree_id == "ree"
    assert result.attributions[0].ree_support
    assert result.events[-1].execution_id is None
    assert result.unassigned


def test_receipt_reference_does_not_attribute_old_operation_to_current_workbench(tmp_path):
    old = operation(1, None)
    current = state()
    current["state"]["audit"]["build"]["receipt_run_id"] = "run-1"
    result = assemble_recording(recording(tmp_path, [old], [current]))
    assert len(result.events) == 4
    assert len(result.ree_histories[0].event_ids) == 4
    assert len(result.executions[0].events) == 1
    assert all(event.execution_id is None for event in result.events[:3])


def test_canonical_events_include_ree_access_after_release(tmp_path):
    outside = operation(2, None)
    outside["name"] = "GET sealed REE"
    result = assemble_recording(recording(tmp_path, [operation(1, "wb"), outside]))
    assert len(result.events) == 4
    assert len(result.ree_histories[0].event_ids) == 4
    assert result.events[-1].execution_id is None
    assert len(result.executions[0].events) == 3
    assert not result.unassigned
    data = json.loads(result.model_dump_json())
    assert data["schema_version"] == 2
