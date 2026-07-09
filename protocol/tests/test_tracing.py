from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from opentelemetry import context
from opentelemetry.proto.common.v1.common_pb2 import AnyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    Status,
    StatusCode,
    TraceFlags,
    set_span_in_context,
)

from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    _anyvalue,
    _format_relayed_span,
    attach_remote_context,
    command_metric_attrs,
    current_trace_context,
    current_traceparent,
    detach_context,
    record_command_status,
    record_ree_id,
)


@dataclass
class _FakeSpan:
    attributes: dict[str, str] = field(default_factory=dict)
    status: Status | None = None

    def set_attribute(self, key: str, value: str) -> None:
        self.attributes[key] = value

    def set_status(self, status: StatusCode, description: str | None = None) -> None:
        self.status = Status(status, description)


def _attach_span(trace_id: int, span_id: int) -> object:
    span_context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=None,
    )
    return context.attach(set_span_in_context(NonRecordingSpan(span_context)))


def test_command_span_attrs_apply_only_present_identity_fields() -> None:
    span = _FakeSpan()
    protocol_span = cast(Span, span)

    CommandSpanAttrs(operation="build_runtime", run_id="run-1").apply(protocol_span)
    record_ree_id(protocol_span, "ree-1")

    assert span.attributes == {
        "repo2ree.operation": "build_runtime",
        "repo2ree.run_id": "run-1",
        "repo2ree.ree_id": "ree-1",
    }


def test_record_command_status_marks_failures_as_span_errors() -> None:
    span = _FakeSpan()

    record_command_status(cast(Span, span), "failed")

    assert span.attributes["repo2ree.status"] == "failed"
    assert span.status is not None
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "failed"


def test_record_command_status_leaves_successful_span_status_unset() -> None:
    span = _FakeSpan()

    record_command_status(cast(Span, span), "succeeded")

    assert span.attributes["repo2ree.status"] == "succeeded"
    assert span.status is None


def test_command_metric_attrs_uses_protocol_attribute_namespace() -> None:
    assert command_metric_attrs("run_experiment", status="cancelled") == {
        "repo2ree.operation": "run_experiment",
        "repo2ree.status": "cancelled",
    }
    assert command_metric_attrs("run_experiment") == {"repo2ree.operation": "run_experiment"}


def test_current_trace_context_and_traceparent_use_active_span() -> None:
    trace_id = 0x11111111111111111111111111111111
    span_id = 0x2222222222222222
    token = _attach_span(trace_id, span_id)
    try:
        assert current_trace_context() == (
            "11111111111111111111111111111111",
            "2222222222222222",
        )
        assert current_traceparent() == ("00-11111111111111111111111111111111-2222222222222222-01")
    finally:
        context.detach(token)  # type: ignore[arg-type]


def test_attach_remote_context_round_trips_traceparent() -> None:
    traceparent = "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01"
    token = attach_remote_context(traceparent)
    try:
        assert current_trace_context() == (
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "bbbbbbbbbbbbbbbb",
        )
    finally:
        detach_context(token)

    assert attach_remote_context(None) is None
    detach_context(None)


def test_format_relayed_span_renders_scalar_attributes() -> None:
    span = PbSpan(
        name="executor.run",
        trace_id=bytes.fromhex("0f" * 16),
        span_id=bytes.fromhex("1e" * 8),
        parent_span_id=bytes.fromhex("2d" * 8),
    )
    span.attributes.add(key="repo2ree.operation", value=AnyValue(string_value="run_experiment"))
    span.attributes.add(key="retry_count", value=AnyValue(int_value=2))
    span.attributes.add(key="cached", value=AnyValue(bool_value=True))
    span.attributes.add(key="duration", value=AnyValue(double_value=1.25))

    assert _format_relayed_span(span) == {
        "name": "executor.run",
        "trace_id": "0f" * 16,
        "span_id": "1e" * 8,
        "parent_id": "2d" * 8,
        "attributes": {
            "repo2ree.operation": "run_experiment",
            "retry_count": 2,
            "cached": True,
            "duration": 1.25,
        },
    }


def test_format_relayed_span_uses_none_for_missing_parent() -> None:
    span = PbSpan(name="root", trace_id=bytes.fromhex("01" * 16), span_id=bytes.fromhex("02" * 8))

    assert _format_relayed_span(span)["parent_id"] is None


def test_anyvalue_falls_back_for_non_scalar_values() -> None:
    value = AnyValue()
    value.array_value.values.add(string_value="nested")

    assert _anyvalue(value) == str(value)
