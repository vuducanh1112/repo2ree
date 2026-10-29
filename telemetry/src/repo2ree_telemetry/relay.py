"""Span relays for processes with no path to a collector, and the sinks relayed spans land in."""

from __future__ import annotations

import base64
import json
import logging
import os
import queue
import sys
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from repo2ree_telemetry.bootstrap import TRACE_FILE_ENV, append_trace_lines, build_resource, get_meter
from repo2ree_telemetry.relayed_json import decode_relayed_spans, relayed_span_json, relayed_span_summary

logger = logging.getLogger(__name__)


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
    provider = TracerProvider(resource=build_resource(service_name))
    provider.add_span_processor(SimpleSpanProcessor(_RelaySpanExporter(stream)))
    trace.set_tracer_provider(provider)


class _CallbackSpanExporter(SpanExporter):
    """Hand each finished batch to ``send`` as one base64 OTLP payload.

    The same encoding as ``_RelaySpanExporter``, a different egress. The
    executor writes to a stream it owns and that is open for its whole short
    life; a resident service hands bytes to a socket that may not be connected
    yet — including the dial span describing the very connection the payload
    will travel on. So this one buffers rather than drops: ``send`` returns
    False while there is no connection and the payload waits for one.

    Always reports SUCCESS. ``BatchSpanProcessor`` discards a FAILURE instead of
    retrying it, so the retry has to live here or not at all. The buffer is
    bounded and oldest-first: a service that never connects sheds its earliest
    spans rather than growing without limit.
    """

    def __init__(self, send: Callable[[str], bool], *, max_buffer: int = 256):
        self._send = send
        self._buffer: deque[str] = deque(maxlen=max_buffer)
        self._lock = threading.Lock()

    def export(self, spans: list[ReadableSpan]) -> SpanExportResult:  # type: ignore[override]
        payload = base64.b64encode(encode_spans(spans).SerializeToString()).decode("ascii")
        with self._lock:
            dropped = len(self._buffer) == self._buffer.maxlen
            self._buffer.append(payload)
            if dropped:
                _relay_drop_counter.add(1, {"reason": "buffer_full"})
            # Oldest first, stopping at the first refusal: ordering holds, and a
            # disconnected socket costs one check per batch rather than a walk
            # of the whole buffer.
            while self._buffer and self._send(self._buffer[0]):
                self._buffer.popleft()
        return SpanExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        with self._lock:
            while self._buffer and self._send(self._buffer[0]):
                self._buffer.popleft()
            return not self._buffer

    def shutdown(self) -> None:
        pass


def setup_relayed_span_export(
    service_name: str,
    send: Callable[[str], bool],
    *,
    instance_id: str | None = None,
) -> TracerProvider:
    """Bootstrap tracing for a service that relays its own spans over its socket.

    The counterpart of ``setup_tracing`` for a process that holds a control-plane
    connection but no path to a collector. Spans ride the socket the service
    already dials, as executor spans ride the stderr the executor already writes
    — see ``setup_relay_tracing``.

    ``BatchSpanProcessor``, not the executor's ``SimpleSpanProcessor``: this
    process is long-lived, so batching is worth it, and ``shutdown()`` flushes
    what is queued. Buffering across a disconnect is the exporter's job.
    """
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(resource=build_resource(service_name, instance_id))
    provider.add_span_processor(BatchSpanProcessor(_CallbackSpanExporter(send)))
    trace.set_tracer_provider(provider)
    return provider


_relay_drop_counter = get_meter(__name__).create_counter(
    "workbench.span_relay_drop",
    description="Number of executor spans dropped instead of forwarded to the collector.",
)


def _otlp_headers_from_env() -> dict[str, str]:
    """Parse ``OTEL_EXPORTER_OTLP_HEADERS`` (``k=v,k2=v2``) into a dict.

    The SDK exporters read this env var themselves; this mirrors it for the
    hand-rolled relay POST so collectors that authenticate ingest (e.g.
    ClickStack's ingestion API key) accept relayed executor spans too.
    """
    raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        key, sep, value = pair.partition("=")
        if sep and key.strip():
            headers[key.strip()] = value.strip()
    return headers


def forward_relayed_spans(payloads: list[str], endpoint: str) -> None:
    """POST relayed span payloads to the OTLP/HTTP collector.

    Each payload is base64 OTLP protobuf produced by ``_RelaySpanExporter``.
    Failures are logged, never raised — span egress must not break command flow.
    """
    if not payloads:
        return
    import requests

    url = f"{endpoint}/v1/traces"
    headers = {"Content-Type": "application/x-protobuf", **_otlp_headers_from_env()}
    for payload in payloads:
        try:
            resp = requests.post(
                url,
                data=base64.b64decode(payload),
                headers=headers,
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
    if not console_fallback:
        return None
    if trace_file := os.environ.get(TRACE_FILE_ENV):
        return _BackgroundSpanForwarder(_relayed_file_sink(Path(trace_file))).submit
    return _BackgroundSpanForwarder(_relayed_console_sink).submit


def _relayed_file_sink(path: Path) -> SpanSink:
    """Append relayed spans to *path* in the host exporter's own JSON shape.

    The counterpart of :class:`_FileSpanExporter`, and deliberately writing the
    same shape: host and workbench spans land in one file, and a reader that can
    parse one line can parse them all. Anything less makes the file two formats
    wearing one extension.

    Takes its path at construction, as ``_FileSpanExporter`` does, so the
    destination is fixed when the sink is built rather than re-read per batch.
    """

    def _write(payloads: list[str]) -> None:
        lines = [json.dumps(relayed_span_json(span, resource)) for resource, span in decode_relayed_spans(payloads)]
        if lines:
            append_trace_lines(path, lines)

    return _write


def _relayed_console_sink(payloads: list[str]) -> None:
    """Print relayed spans to stdout, one skimmable line each.

    The counterpart of ``ConsoleSpanExporter``. Compact on purpose: this output
    scrolls past a human watching a dev server, where a full span per line is
    noise. Nothing reads it back, which is what makes dropping fields safe here
    and unsafe in the file sink.
    """
    for _resource, span in decode_relayed_spans(payloads):
        print(json.dumps(relayed_span_summary(span)), file=sys.stdout, flush=True)  # noqa: T201 — the console span sink's whole job is writing spans to stdout
