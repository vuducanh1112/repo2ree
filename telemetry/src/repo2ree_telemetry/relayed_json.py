"""Relayed OTLP protobuf spans, decoded and rendered as the SDK's own JSON."""

from __future__ import annotations

import base64
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue as _PbAnyValue
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource as _PbResource
    from opentelemetry.proto.trace.v1.trace_pb2 import Span as _PbSpan


logger = logging.getLogger(__name__)


def decode_relayed_spans(payloads: list[str]) -> list[tuple[_PbResource, _PbSpan]]:
    """Decode base64 OTLP payloads into ``(resource, span)`` pairs.

    The relay carries executor spans as base64 OTLP protobuf so the supervisor
    can forward bytes to a collector without understanding them. With no
    collector we decode here instead. Host-side only: nothing on the executor
    or workbench side ever calls it, which is why ``opentelemetry-proto`` is
    imported here rather than at module scope. Never raises: span egress must
    not break command flow.

    Spans are paired with their resource because ``service.name`` lives there,
    one level up from the span, and a span that cannot say which service emitted
    it is not much use to a reader.
    """
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    decoded: list[tuple[_PbResource, _PbSpan]] = []
    for payload in payloads:
        try:
            request = ExportTraceServiceRequest()
            request.ParseFromString(base64.b64decode(payload))
        except Exception as exc:  # noqa: BLE001 — a malformed payload must not break dispatch
            logger.warning("failed to decode relayed spans: %s", exc)
            continue
        for resource_spans in request.resource_spans:
            for scope_spans in resource_spans.scope_spans:
                decoded.extend((resource_spans.resource, span) for span in scope_spans.spans)
    return decoded


_SPAN_KIND_NAMES = {
    0: "SpanKind.INTERNAL",  # UNSPECIFIED — the SDK has no such kind and defaults to INTERNAL
    1: "SpanKind.INTERNAL",
    2: "SpanKind.SERVER",
    3: "SpanKind.CLIENT",
    4: "SpanKind.PRODUCER",
    5: "SpanKind.CONSUMER",
}


_STATUS_CODE_NAMES = {0: "UNSET", 1: "OK", 2: "ERROR"}


def relayed_span_json(span: _PbSpan, resource: _PbResource) -> dict[str, object]:
    """Render a decoded protobuf span exactly as ``ReadableSpan.to_json`` would."""
    from opentelemetry.sdk.util import ns_to_iso_str

    status: dict[str, object] = {"status_code": _STATUS_CODE_NAMES.get(span.status.code, "UNSET")}
    if span.status.message:
        status["description"] = span.status.message
    return {
        "name": span.name,
        "context": {
            "trace_id": f"0x{span.trace_id.hex()}",
            "span_id": f"0x{span.span_id.hex()}",
            "trace_state": "[]",
        },
        "kind": _SPAN_KIND_NAMES.get(span.kind, "SpanKind.INTERNAL"),
        "parent_id": f"0x{span.parent_span_id.hex()}" if span.parent_span_id else None,
        "start_time": ns_to_iso_str(span.start_time_unix_nano),
        "end_time": ns_to_iso_str(span.end_time_unix_nano),
        "status": status,
        "attributes": _attributes(span.attributes),
        "events": [
            {
                "name": event.name,
                "timestamp": ns_to_iso_str(event.time_unix_nano),
                "attributes": _attributes(event.attributes),
            }
            for event in span.events
        ],
        "links": [
            {
                "context": {
                    "trace_id": f"0x{link.trace_id.hex()}",
                    "span_id": f"0x{link.span_id.hex()}",
                    "trace_state": "[]",
                },
                "attributes": _attributes(link.attributes),
            }
            for link in span.links
        ],
        "resource": {"attributes": _attributes(resource.attributes), "schema_url": ""},
    }


def relayed_span_summary(span: _PbSpan) -> dict[str, object]:
    """The few fields of a relayed span worth a line on a watched console."""
    return {
        "name": span.name,
        "trace_id": span.trace_id.hex(),
        "span_id": span.span_id.hex(),
        "parent_id": span.parent_span_id.hex() or None,
        "attributes": _attributes(span.attributes),
    }


def _attributes(keyvalues: Iterable[Any]) -> dict[str, object]:
    return {kv.key: _anyvalue(kv.value) for kv in keyvalues}


def _anyvalue(value: _PbAnyValue) -> object:
    """Unwrap an OTLP protobuf AnyValue to its Python scalar."""
    if value.HasField("string_value"):
        return value.string_value
    if value.HasField("int_value"):
        return value.int_value
    if value.HasField("bool_value"):
        return value.bool_value
    if value.HasField("double_value"):
        return value.double_value
    return str(value)
