"""Tracing bootstrap and cross-process context propagation.

``setup_tracing`` is the one-shot bootstrap each process entry point calls
(api lifespan, executor main), mirroring ``configure_logging``. The
inject/attach helpers carry a W3C ``traceparent`` across the ``docker exec``
boundary so the executor's spans hang under the host-side dispatch span
instead of forming a disjoint tree.

The OpenTelemetry dependency is owned here so callers (supervisor, executor)
never import ``opentelemetry`` directly.
"""

from __future__ import annotations

import base64
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TextIO

from opentelemetry import context, trace

if TYPE_CHECKING:
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue as _PbAnyValue
    from opentelemetry.proto.trace.v1.trace_pb2 import Span as _PbSpan
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Span, Tracer

# ``requests`` and the OTLP/HTTP exporter live behind the host-side functions
# (setup_tracing, forward_relayed_spans) so the executor — which only streams
# spans for relay — doesn't drag them into the minimal workbench image.

logger = logging.getLogger(__name__)

# Attribute namespace — single source of truth for the `repo2ree.*` keys.
_ATTR_OPERATION = "repo2ree.operation"
_ATTR_RUN_ID = "repo2ree.run_id"
_ATTR_REE_ID = "repo2ree.ree_id"
_ATTR_STATUS = "repo2ree.status"

# ================================================
# Bootstrap
# ================================================


def setup_tracing(
    service_name: str,
    *,
    endpoint: str | None = None,
    console_fallback: bool = False,
) -> None:
    """Configure the global TracerProvider once for this process.

    Exports via OTLP/HTTP to ``endpoint/v1/traces`` when provided. Otherwise,
    if ``console_fallback`` is enabled, spans print to stdout for local dev; if
    not, tracing stays a no-op. The executor leaves the fallback off because its
    stdout/stderr carry the ActionResult/NDJSON protocol — console spans there
    would corrupt the stream.
    """
    if not endpoint and not console_fallback:
        return

    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> Tracer:
    """Return a tracer for the given module name (use ``__name__``)."""
    return trace.get_tracer(name)


# ================================================
# Span attributes
# ================================================


@dataclass(frozen=True, slots=True)
class CommandSpanAttrs:
    """Identity attributes for a command/dispatch span.

    Owns the ``repo2ree.*`` attribute namespace so call sites pass typed fields
    instead of stringly-keyed ``set_attribute`` calls. Status is recorded
    separately via ``record_command_status`` once the command completes.
    """

    operation: str
    run_id: str
    ree_id: str | None = None

    def apply(self, span: Span) -> None:
        span.set_attribute(_ATTR_OPERATION, self.operation)
        span.set_attribute(_ATTR_RUN_ID, self.run_id)
        if self.ree_id is not None:
            span.set_attribute(_ATTR_REE_ID, self.ree_id)


def record_command_status(span: Span, status: str) -> None:
    """Record the terminal status of a command on its span."""
    span.set_attribute(_ATTR_STATUS, status)


def record_ree_id(span: Span, ree_id: str) -> None:
    """Tag a span with the REE it operates on."""
    span.set_attribute(_ATTR_REE_ID, ree_id)


# ================================================
# Executor relay (egress via the supervisor)
# ================================================


class _RelaySpanExporter(SpanExporter):
    """Serialise finished spans onto a text stream as NDJSON for relay.

    The executor runs inside the dind workbench container with no path to the
    collector, so instead of exporting directly it writes each span batch as a
    ``{"type": "span", ...}`` event on the same stderr stream that already
    carries log events. The supervisor parses these and forwards them. The
    payload is base64-wrapped OTLP protobuf, so the supervisor relays bytes
    without needing to understand them.
    """

    def __init__(self, stream: TextIO):
        self._stream = stream

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:  # type: ignore[override]
        payload = base64.b64encode(encode_spans(spans).SerializeToString()).decode("ascii")
        self._stream.write(json.dumps({"type": "span", "payload": payload}) + "\n")
        self._stream.flush()
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

    def shutdown(self) -> None:
        pass


def setup_relay_tracing(service_name: str, stream: TextIO) -> None:
    """Bootstrap tracing for the executor: stream spans for supervisor relay.

    Uses ``SimpleSpanProcessor`` so each span is emitted as it ends, before the
    process exits and the stream closes.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(SimpleSpanProcessor(_RelaySpanExporter(stream)))
    trace.set_tracer_provider(provider)


def forward_relayed_spans(payloads: list[str], endpoint: str) -> None:
    """POST relayed span payloads to the OTLP/HTTP collector.

    Each payload is base64 OTLP protobuf produced by ``_RelaySpanExporter``.
    Failures are logged, never raised — span egress must not break command flow.
    """
    if not payloads:
        return
    import requests

    url = f"{endpoint}/v1/traces"
    for payload in payloads:
        try:
            requests.post(
                url,
                data=base64.b64decode(payload),
                headers={"Content-Type": "application/x-protobuf"},
                timeout=5,
            )
        except (requests.RequestException, ValueError) as exc:
            logger.warning("failed to relay spans to %s: %s", url, exc)


# Callable type for the workbench span relay sink injected into WorkbenchManager.
# The manager collects relayed payloads from executor stderr and passes the full
# list here once the command completes. Where they go (collector, console, /dev/null)
# is entirely the caller's decision.
SpanSink = Callable[[list[str]], None]


def build_span_sink(endpoint: str | None, *, console_fallback: bool = False) -> SpanSink | None:
    """Return the sink the manager hands relayed executor spans to, or None.

    Mirrors ``setup_tracing``: forwards to the OTLP collector at ``endpoint`` when
    set; otherwise, if ``console_fallback`` is on, decodes and prints spans to
    stdout for local dev; otherwise returns None. Inject the result into
    ``WorkbenchManager`` so the API composition root decides where executor spans
    go. A None sink means the manager never activates the relay (``TRACE_RELAY``
    is not injected, so the executor's tracer stays a no-op).
    """
    if endpoint:
        _ep = endpoint

        def _forward(payloads: list[str]) -> None:
            forward_relayed_spans(payloads, _ep)

        return _forward
    if console_fallback:
        return _console_span_sink
    return None


def _console_span_sink(payloads: list[str]) -> None:
    """Decode relayed OTLP payloads and print them to stdout for local dev.

    The relay carries executor spans as base64 OTLP protobuf so the supervisor
    can forward bytes to a collector without understanding them. With no collector
    we instead decode here and print, so workbench spans land in the same stdout
    the API's ConsoleSpanExporter writes to. Host-side only — relies on
    ``opentelemetry-proto``, which the minimal workbench image deliberately lacks.
    Never raises: span egress must not break command flow.
    """
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    for payload in payloads:
        try:
            request = ExportTraceServiceRequest()
            request.ParseFromString(base64.b64decode(payload))
        except Exception as exc:  # noqa: BLE001 — a malformed payload must not break dispatch
            logger.warning("failed to decode relayed spans for console: %s", exc)
            continue
        for resource_spans in request.resource_spans:
            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    print(json.dumps(_format_relayed_span(span)), file=sys.stdout, flush=True)


def _format_relayed_span(span: _PbSpan) -> dict[str, object]:
    """Render a decoded protobuf span as a compact dict for console output."""
    return {
        "name": span.name,
        "trace_id": span.trace_id.hex(),
        "span_id": span.span_id.hex(),
        "parent_id": span.parent_span_id.hex() or None,
        "attributes": {kv.key: _anyvalue(kv.value) for kv in span.attributes},
    }


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


# ================================================
# Cross-process propagation
# ================================================


def current_traceparent() -> str | None:
    """Serialise the active span context as a W3C traceparent, or None."""
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier.get("traceparent")


def attach_remote_context(traceparent: str | None) -> object | None:
    """Make the remote traceparent the current context; return a detach token.

    Pass the token to ``detach_context`` when the unit of work completes. Returns
    None when there is nothing to attach.
    """
    if not traceparent:
        return None
    ctx = extract({"traceparent": traceparent})
    return context.attach(ctx)


def detach_context(token: object | None) -> None:
    """Detach a context previously attached via ``attach_remote_context``."""
    if token is not None:
        context.detach(token)  # type: ignore[arg-type]
