from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.result import ActionResult, HistoryReference
from repo2ree_telemetry.tracing import record_result_evidence, record_span_facts


def test_result_evidence_survives_wire_and_bounded_span_facts():
    context = ExecutionContext.new(ree_id="ree-1")
    result = ActionResult(
        status="succeeded",
        context=context,
        outputs={"value": "domain output"},
        history=HistoryReference(
            selection_version=1,
            attempt_id=context.attempt_id,
            scope=".",
            capture_status="captured",
            operation_status="succeeded",
            changed=False,
            before_snapshot_id="before",
            after_snapshot_id="after",
        ),
    )
    assert ActionResult.model_validate_json(result.model_dump_json()) == result
    assert "history" not in result.outputs
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer("test").start_as_current_span("operation") as span:
        record_span_facts(span, {f"input_{i}": i for i in range(100)}, namespace="arg")
        record_span_facts(span, {f"output_{i}": i for i in range(100)}, namespace="output")
        record_result_evidence(span, result)
    attrs = exporter.get_finished_spans()[0].attributes
    assert attrs is not None
    assert attrs["repo2ree.attempt_id"] == context.attempt_id
    assert attrs["repo2ree.operation_id"] == context.operation_id
    assert attrs["repo2ree.history.after_snapshot_id"] == "after"
    assert attrs["repo2ree.history.changed"] is False
    provider.shutdown()
