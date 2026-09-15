"""The functional core runs on values and does not depend on an active recording."""

import ast
import builtins
import copy
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from repo2ree_history.core.assembly import assemble, build_events
from repo2ree_history.core.evidence import RecordingSnapshot, SourceDocument
from repo2ree_history.core.models import (
    Artifact,
    OperationCompleted,
    OperationStarted,
    Producer,
    Resources,
    SourceReference,
    SpanLocator,
    TraceContext,
)
from repo2ree_history.core.normalize import node
from repo2ree_history.core.report import render_outputs


def snapshot() -> RecordingSnapshot:
    document = {
        "name": "command.build",
        "context": {"trace_id": "1" * 32, "span_id": "2" * 16},
        "attributes": {
            "repo2ree.operation_id": "op",
            "repo2ree.attempt_id": "attempt",
            "repo2ree.operation": "build",
            "repo2ree.workbench_id": "wb",
            "repo2ree.status": "succeeded",
        },
        "resource": {"attributes": {"service.name": "repo2ree-exec"}},
    }
    ref = SourceReference(artifact_id="traces", locator=SpanLocator(trace_id="1" * 32, span_id="2" * 16, line=1))
    return RecordingSnapshot(
        "/unavailable-recording",
        {"execution_id": "invocation", "nodeid": "test", "started": 0, "finished": 1, "repositories": []},
        (Artifact(artifact_id="traces", kind="telemetry", uri="traces.ndjson"),),
        spans=(SourceDocument(document, ref),),
    )


def test_core_assembles_and_renders_without_io_or_input_mutation(monkeypatch):
    recording = snapshot()
    before = copy.deepcopy(recording)

    def forbidden(*args, **kwargs):
        pytest.fail("functional core attempted external I/O")

    with monkeypatch.context() as blocked:
        blocked.setattr(builtins, "open", forbidden)
        blocked.setattr(Path, "open", forbidden)
        blocked.setattr(Path, "resolve", forbidden)
        blocked.setattr(subprocess, "run", forbidden)
        first = assemble(recording)
        second = assemble(recording)
        files = render_outputs(first)
        assert first == second
        assert files == render_outputs(second)
    assert recording == before
    assert {"assembly.json", "evidence-report.md", "sequence.md"} <= files.keys()
    assert len(first.executions[0].events) == 3


def test_same_span_id_in_different_traces_does_not_cross_bind_causes():
    ref = snapshot().spans[0].source
    trace_a = TraceContext(trace_id="a" * 32, span_id="1" * 16)
    trace_b = TraceContext(trace_id="b" * 32, span_id="1" * 16)
    producer, resources = Producer(component="executor"), Resources(workbench_id="wb")
    operation = assemble(snapshot()).executions[0].events[0].operation
    nodes = (
        node(ref, producer, OperationStarted(), resources, operation, trace=trace_a),
        node(ref, producer, OperationStarted(), resources, operation, trace=trace_b),
        node(ref, producer, OperationCompleted(outcome="succeeded"), resources, operation, trace=trace_a),
        node(ref, producer, OperationCompleted(outcome="succeeded"), resources, operation, trace=trace_b),
    )
    events, _ = build_events(nodes, (0, 1, 2, 3), "execution")
    assert events[2].causes == (events[0].event_id,)
    assert events[3].causes == (events[1].event_id,)


def test_unassigned_duplicate_exports_preserve_all_locations():
    recording = snapshot()
    document = copy.deepcopy(recording.spans[0].document)
    document["attributes"].pop("repo2ree.workbench_id")
    first = recording.spans[0].source
    second = first.model_copy(update={"locator": first.locator.model_copy(update={"line": 2})})
    recording = replace(recording, spans=(SourceDocument(document, first), SourceDocument(document, second)))
    result = assemble(recording)
    assert not result.executions
    assert all(item.source_refs == (first, second) for item in result.unassigned)


def test_core_cannot_call_ambient_effect_builtins():
    # Import contracts cover shell and I/O modules; this covers implicit builtins and clocks.
    root = Path(__file__).parents[1] / "src/repo2ree_history/core"
    forbidden = {"open", "input", "print", "exec", "eval", "__import__"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for call in (item for item in ast.walk(tree) if isinstance(item, ast.Call)):
            if isinstance(call.func, ast.Name):
                assert call.func.id not in forbidden, f"{path}:{call.lineno}: effectful builtin"
            elif isinstance(call.func, ast.Attribute):
                assert call.func.attr not in {"now", "utcnow", "today"}, f"{path}:{call.lineno}: ambient clock"
