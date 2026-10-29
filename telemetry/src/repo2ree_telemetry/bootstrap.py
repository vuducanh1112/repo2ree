"""Process bootstrap: the tracer, meter, and logger providers and where they export."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.metrics import Meter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace import TracerProvider as TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Tracer

if TYPE_CHECKING:
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.metrics import MeterProvider


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


def build_resource(service_name: str, instance_id: str | None = None) -> Resource:
    """Resource identity shared by every provider in this process.

    Beyond ``service.name`` we surface version and environment when present so
    dashboards can slice by deploy. Both are optional env vars — unset in local
    dev, injected in deployed environments.

    ``instance_id`` becomes ``service.instance.id`` (the semconv instance
    attribute) for services that run as several identical processes — the
    workbench passes its persistent workbench id so every span, metric, and
    log it emits is attributable to one workbench without per-callsite plumbing.
    """
    attrs: dict[str, str] = {"service.name": service_name}
    if instance_id:
        attrs["service.instance.id"] = instance_id
    if version := os.environ.get("SERVICE_VERSION"):
        attrs["service.version"] = version
    if environment := os.environ.get("DEPLOY_ENV"):
        attrs["deployment.environment"] = environment
    resource = Resource.create(attrs)
    if instance_id:
        return resource
    # The SDK (1.45+) fills in a random service.instance.id per process. An id here
    # names one of several identical processes; a single service gets none, rather
    # than a new one on every restart.
    attributes = {key: value for key, value in resource.attributes.items() if key != "service.instance.id"}
    return Resource(attributes, resource.schema_url)


# When set, spans produced without a collector append to this path as one
# JSON object per line instead of printing to stdout — a durable, greppable
# record of what a dev server run or an integration test did.
TRACE_FILE_ENV = "TRACE_FILE"


def append_trace_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(line + "\n" for line in lines)


class _FileSpanExporter(SpanExporter):
    """Append finished spans to a file as one JSON object per line."""

    def __init__(self, path: Path):
        self._path = path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        append_trace_lines(self._path, [span.to_json(indent=None) for span in spans])
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def setup_tracing(
    service_name: str,
    *,
    endpoint: str | None = None,
    console_fallback: bool = False,
    instance_id: str | None = None,
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

    provider = TracerProvider(resource=build_resource(service_name, instance_id))
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    elif trace_file := os.environ.get(TRACE_FILE_ENV):
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
    instance_id: str | None = None,
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
        resource=build_resource(service_name, instance_id),
        metric_readers=[reader],
        views=[duration_view],
    )
    metrics.set_meter_provider(provider)
    return provider


def get_meter(name: str) -> Meter:
    """Return a meter for the given module name (use ``__name__``)."""
    return metrics.get_meter(name)


def setup_logs(
    service_name: str,
    *,
    endpoint: str | None = None,
    instance_id: str | None = None,
) -> LoggerProvider | None:
    """Configure the global LoggerProvider once for this process.

    Exports via OTLP/HTTP to ``endpoint/v1/logs`` when provided; otherwise
    stays a no-op. Call alongside ``setup_tracing`` from the same process
    entry point, then attach ``otlp_log_handler(provider)`` to the root
    logger (``configure_logging`` does this) so standard ``logging`` records
    ship to the collector — stamped with the active span's trace context by
    the handler, which is what makes trace → logs navigation work.

    Returns the provider so the caller can shut it down on clean exit,
    flushing any buffered records. Returns None when logs are a no-op.
    """
    if not endpoint:
        return None

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    provider = LoggerProvider(resource=build_resource(service_name, instance_id))
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs")))
    set_logger_provider(provider)
    return provider


def otlp_log_handler(provider: LoggerProvider) -> logging.Handler:
    """Return a ``logging.Handler`` that exports records via *provider*.

    Owned here so callers (``log.py``, entry points) never import
    ``opentelemetry`` directly.
    """
    from opentelemetry.instrumentation.logging.handler import LoggingHandler

    return LoggingHandler(logger_provider=provider)
