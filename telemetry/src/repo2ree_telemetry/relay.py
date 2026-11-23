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
    provider = TracerProvider(resource=build_resource(service_name))
    provider.add_span_processor(SimpleSpanProcessor(_RelaySpanExporter(stream)))
    trace.set_tracer_provider(provider)


class _CallbackSpanExporter(SpanExporter):
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
    raw = os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers: dict[str, str] = {}
    for pair in raw.split(","):
        key, sep, value = pair.partition("=")
        if sep and key.strip():
            headers[key.strip()] = value.strip()
    return headers


def forward_relayed_spans(payloads: list[str], endpoint: str) -> None:
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
    def __init__(self, forward: SpanSink, *, max_queue: int = 1024):
        self._forward = forward
        self._queue: queue.Queue[list[str]] = queue.Queue(maxsize=max_queue)
        self._thread = threading.Thread(target=self._run, name="span-relay-forwarder", daemon=True)
        self._starting = threading.Lock()

    def submit(self, payloads: list[str]) -> None:
        if not payloads:
            return
        with self._starting:
            if self._thread.ident is None:
                self._thread.start()
        try:
            self._queue.put_nowait(payloads)
        except queue.Full:
            _relay_drop_counter.add(len(payloads), {"reason": "queue_full"})

    def _run(self) -> None:
        while True:
            payloads = self._queue.get()
            try:
                self._forward(payloads)
            except Exception as exc:  # noqa: BLE001
                logger.warning("span relay forward failed: %s", exc)
            finally:
                self._queue.task_done()


SpanSink = Callable[[list[str]], None]


def build_span_sink(endpoint: str | None, *, console_fallback: bool = False) -> SpanSink | None:
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
    def _write(payloads: list[str]) -> None:
        lines = [json.dumps(relayed_span_json(span, resource)) for resource, span in decode_relayed_spans(payloads)]
        if lines:
            append_trace_lines(path, lines)

    return _write


def _relayed_console_sink(payloads: list[str]) -> None:
    for _resource, span in decode_relayed_spans(payloads):
        print(json.dumps(relayed_span_summary(span)), file=sys.stdout, flush=True)  # noqa: T201
