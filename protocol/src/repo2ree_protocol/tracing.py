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
import os
import queue
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from opentelemetry import context, metrics, trace

if TYPE_CHECKING:
    from opentelemetry.proto.common.v1.common_pb2 import AnyValue as _PbAnyValue
    from opentelemetry.proto.trace.v1.trace_pb2 import Span as _PbSpan
    from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.metrics import Meter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Link, Span, StatusCode, Tracer

# ``requests`` and the OTLP/HTTP exporter live behind the host-side functions
# (setup_tracing, forward_relayed_spans) so the executor — which only streams
# spans for relay — doesn't drag them into the minimal workbench image.

logger = logging.getLogger(__name__)

# Attribute namespace — single source of truth for the `repo2ree.*` keys.
_ATTR_OPERATION = "repo2ree.operation"
_ATTR_RUN_ID = "repo2ree.run_id"
_ATTR_REE_ID = "repo2ree.ree_id"
_ATTR_STATUS = "repo2ree.status"

# Explicit histogram buckets (seconds) for every `*_seconds` instrument. The
# SDK defaults top out near 10s, but workbench commands (builds, experiments)
# routinely run minutes — without these boundaries everything lands in the
# +Inf bucket and p95/p99 become meaningless. Spans second-to-minutes work.
_DURATION_BUCKETS_SECONDS = (
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    1200.0,
)


def _build_resource(service_name: str) -> Resource:
    """Resource identity shared by every provider in this process.

    Beyond ``service.name`` we surface version and environment when present so
    dashboards can slice by deploy. Both are optional env vars — unset in local
    dev, injected in deployed environments.
    """
    attrs: dict[str, str] = {"service.name": service_name}
    if version := os.environ.get("SERVICE_VERSION"):
        attrs["service.version"] = version
    if environment := os.environ.get("DEPLOY_ENV"):
        attrs["deployment.environment"] = environment
    return Resource.create(attrs)


# ================================================
# Local span sink (no collector)
# ================================================

# When set, spans produced without a collector append to this path as one
# JSON object per line instead of printing to stdout — a durable, greppable
# record of what a dev server run or an integration test did.
_TRACE_FILE_ENV = "TRACE_FILE"


def _append_trace_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(line + "\n" for line in lines)


class _FileSpanExporter(SpanExporter):
    """Append finished spans to a file as one JSON object per line."""

    def __init__(self, path: Path):
        self._path = path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        _append_trace_lines(self._path, [span.to_json(indent=None) for span in spans])
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


# ================================================
# Bootstrap
# ================================================


def setup_tracing(
    service_name: str,
    *,
    endpoint: str | None = None,
    console_fallback: bool = False,
) -> TracerProvider | None:
    """Configure the global TracerProvider once for this process.

    Exports via OTLP/HTTP to ``endpoint/v1/traces`` when provided. Otherwise,
    if ``console_fallback`` is enabled, spans go to the ``TRACE_FILE`` path
    when that env var is set (one JSON object per line), or print to stdout;
    if not, tracing stays a no-op. The executor leaves the fallback off
    because its stdout/stderr carry the ActionResult/NDJSON protocol — console
    spans there would corrupt the stream.

    Returns the provider so the caller can shut it down on clean exit, flushing
    any buffered spans. Returns None when tracing is a no-op.
    """
    if not endpoint and not console_fallback:
        return None

    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    provider = TracerProvider(resource=_build_resource(service_name))
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    elif trace_file := os.environ.get(_TRACE_FILE_ENV):
        provider.add_span_processor(SimpleSpanProcessor(_FileSpanExporter(Path(trace_file))))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
    trace.set_tracer_provider(provider)
    return provider


def get_tracer(name: str) -> Tracer:
    """Return a tracer for the given module name (use ``__name__``)."""
    return trace.get_tracer(name)


def setup_metrics(
    service_name: str,
    *,
    endpoint: str | None = None,
) -> MeterProvider | None:
    """Configure the global MeterProvider once for this process.

    Exports via OTLP/HTTP to ``endpoint/v1/metrics`` when provided; otherwise
    stays a no-op (counters exist but record nothing). Call alongside
    ``setup_tracing`` from the same process entry point.

    Returns the provider so the caller can shut it down on clean exit, flushing
    any buffered metrics. Returns None when metrics are a no-op.
    """
    if not endpoint:
        return None

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"))
    # Convention: every duration histogram is named ``*_seconds`` and shares the
    # long-tailed bucket set. Counters/gauges are untouched (the view only
    # rebinds histogram aggregation).
    duration_view = View(
        instrument_name="*_seconds",
        aggregation=ExplicitBucketHistogramAggregation(_DURATION_BUCKETS_SECONDS),
    )
    provider = MeterProvider(
        resource=_build_resource(service_name),
        metric_readers=[reader],
        views=[duration_view],
    )
    metrics.set_meter_provider(provider)
    return provider


def get_meter(name: str) -> Meter:
    """Return a meter for the given module name (use ``__name__``)."""
    return metrics.get_meter(name)


# ================================================
# Span attributes
# ================================================


@dataclass(frozen=True, slots=True)
class CommandSpanAttrs:
    """Identity attributes for a command/dispatch span.

    Owns the ``repo2ree.*`` attribute namespace so call sites pass typed fields
    instead of stringly-keyed ``set_attribute`` calls. Status is recorded
    separately via ``record_command_status`` once the command completes.

    ``run_id`` is optional: background runs and workbench dispatches carry one,
    but synchronous REE commands have no run and omit it.
    """

    operation: str
    run_id: str | None = None
    ree_id: str | None = None

    def apply(self, span: Span) -> None:
        span.set_attribute(_ATTR_OPERATION, self.operation)
        if self.run_id is not None:
            span.set_attribute(_ATTR_RUN_ID, self.run_id)
        if self.ree_id is not None:
            span.set_attribute(_ATTR_REE_ID, self.ree_id)


def record_command_status(span: Span, status: str) -> None:
    """Record the terminal status of a command on its span.

    Also flips the span to ERROR when the command didn't succeed, so every
    dispatch layer (core ``command.*``, host ``dispatch_action``, the API
    ``run.*`` root) reports failure consistently — error-rate queries keyed on
    span status would otherwise miss any layer that only set the attribute.
    """
    span.set_attribute(_ATTR_STATUS, status)
    if status != "succeeded":
        span.set_status(StatusCode.ERROR, status)


def record_ree_id(span: Span, ree_id: str) -> None:
    """Tag a span with the REE it operates on."""
    span.set_attribute(_ATTR_REE_ID, ree_id)


def command_metric_attrs(operation: str, *, status: str | None = None) -> dict[str, str]:
    """Build a metric attribute dict using the canonical ``repo2ree.*`` keys.

    Keeps call sites from hardcoding the attribute strings, so the namespace
    owned here stays the single source of truth for metrics as well as spans.
    """
    attrs = {_ATTR_OPERATION: operation}
    if status is not None:
        attrs[_ATTR_STATUS] = status
    return attrs


def current_span_link() -> Link | None:
    """Capture the active span as a Link, or None when there's no valid span.

    Used to bridge two traces that shouldn't share a root — e.g. the HTTP
    request span and a background run span that outlives the response: the run
    anchors its own trace but links back to the request that started it.
    """
    ctx = trace.get_current_span().get_span_context()
    return Link(ctx) if ctx.is_valid else None


def current_trace_context() -> tuple[str, str] | None:
    """Return ``(trace_id, span_id)`` as zero-padded hex for the active span.

    Stamps structured logs with the active trace so logs and traces are
    joinable in the collector. Returns None when there is no recording span
    (e.g. logs emitted outside any request/run). Keeps the OpenTelemetry import
    behind this module so ``log.py`` need not depend on it directly.
    """
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return f"{ctx.trace_id:032x}", f"{ctx.span_id:016x}"


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
    provider = TracerProvider(resource=_build_resource(service_name))
    provider.add_span_processor(SimpleSpanProcessor(_RelaySpanExporter(stream)))
    trace.set_tracer_provider(provider)


_relay_drop_counter = get_meter(__name__).create_counter(
    "workbench.span_relay_drop",
    description="Number of executor spans dropped instead of forwarded to the collector.",
)


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
            resp = requests.post(
                url,
                data=base64.b64decode(payload),
                headers={"Content-Type": "application/x-protobuf"},
                timeout=5,
            )
            resp.raise_for_status()
        except (requests.RequestException, ValueError) as exc:
            _relay_drop_counter.add(1, {"reason": "post_failed"})
            logger.warning("failed to relay spans to %s: %s", url, exc)


class _BackgroundSpanForwarder:
    """Drain relayed span payloads to ``forward`` on a daemon thread.

    Span egress must never sit on the command's critical path: the manager
    enqueues payloads while holding the per-REE lock and reading executor
    output, so a slow collector POST there would inflate ``execute_duration``
    *and* delay other REEs waiting on the lock. Callers ``submit`` payloads
    (non-blocking) and this thread does the network I/O with the sink's own
    deadline. Best-effort: a full queue drops rather than blocks, and the
    daemon thread lets the process exit without joining.
    """

    def __init__(self, forward: SpanSink, *, max_queue: int = 1024):
        self._forward = forward
        self._queue: queue.Queue[list[str]] = queue.Queue(maxsize=max_queue)
        self._thread = threading.Thread(target=self._run, name="span-relay-forwarder", daemon=True)
        self._thread.start()

    def submit(self, payloads: list[str]) -> None:
        if not payloads:
            return
        try:
            self._queue.put_nowait(payloads)
        except queue.Full:
            _relay_drop_counter.add(len(payloads), {"reason": "queue_full"})

    def _run(self) -> None:
        while True:
            payloads = self._queue.get()
            try:
                self._forward(payloads)
            except Exception as exc:  # noqa: BLE001 — egress must never crash the worker
                logger.warning("span relay forward failed: %s", exc)
            finally:
                self._queue.task_done()


# Callable type for the workbench span relay sink injected into WorkbenchManager.
# The manager hands relayed payloads here as they arrive off executor stderr. The
# sink is non-blocking (enqueues for a background thread); where the bytes
# ultimately go (collector, console, /dev/null) is the caller's decision.
SpanSink = Callable[[list[str]], None]


def build_span_sink(endpoint: str | None, *, console_fallback: bool = False) -> SpanSink | None:
    """Return the sink the manager hands relayed executor spans to, or None.

    Mirrors ``setup_tracing``: forwards to the OTLP collector at ``endpoint`` when
    set; otherwise, if ``console_fallback`` is on, decodes spans and writes them
    to the ``TRACE_FILE`` path or stdout for local dev; otherwise returns None. Inject the result into
    ``WorkbenchManager`` so the API composition root decides where executor spans
    go. A None sink means the manager never activates the relay (``TRACE_RELAY``
    is not injected, so the executor's tracer stays a no-op).

    Either sink is wrapped in a ``_BackgroundSpanForwarder`` so the manager's
    ``submit`` call returns immediately and the actual export (network POST or
    protobuf decode + print) happens off the locked, latency-measured path.
    """
    if endpoint:
        _ep = endpoint

        def _forward(payloads: list[str]) -> None:
            forward_relayed_spans(payloads, _ep)

        return _BackgroundSpanForwarder(_forward).submit
    if console_fallback:
        return _BackgroundSpanForwarder(_console_span_sink).submit
    return None


def _console_span_sink(payloads: list[str]) -> None:
    """Decode relayed OTLP payloads for local dev: to TRACE_FILE or stdout.

    The relay carries executor spans as base64 OTLP protobuf so the supervisor
    can forward bytes to a collector without understanding them. With no
    collector we instead decode here and write, so workbench spans land in the
    same place (the ``TRACE_FILE`` path, or stdout) the host's local span
    exporter writes to. Host-side only — relies on ``opentelemetry-proto``,
    which the minimal workbench image deliberately lacks. Never raises: span
    egress must not break command flow.
    """
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

    lines: list[str] = []
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
                    lines.append(json.dumps(_format_relayed_span(span)))

    if trace_file := os.environ.get(_TRACE_FILE_ENV):
        _append_trace_lines(Path(trace_file), lines)
    else:
        for line in lines:
            print(line, file=sys.stdout, flush=True)


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
