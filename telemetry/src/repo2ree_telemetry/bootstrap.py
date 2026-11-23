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
    attributes = {key: value for key, value in resource.attributes.items() if key != "service.instance.id"}
    return Resource(attributes, resource.schema_url)


TRACE_FILE_ENV = "TRACE_FILE"


def append_trace_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.writelines(line + "\n" for line in lines)


class _FileSpanExporter(SpanExporter):
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
    export_timeout: float | None = None,
) -> TracerProvider | None:
    if not endpoint and not console_fallback:
        return None

    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    provider = TracerProvider(resource=build_resource(service_name, instance_id))
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", timeout=export_timeout))
        )
    elif trace_file := os.environ.get(TRACE_FILE_ENV):
        provider.add_span_processor(SimpleSpanProcessor(_FileSpanExporter(Path(trace_file))))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
    trace.set_tracer_provider(provider)
    return provider


def get_tracer(name: str) -> Tracer:
    return trace.get_tracer(name)


def setup_metrics(
    service_name: str,
    *,
    endpoint: str | None = None,
    instance_id: str | None = None,
) -> MeterProvider | None:
    if not endpoint:
        return None

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View

    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"))
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
    return metrics.get_meter(name)


def setup_logs(
    service_name: str,
    *,
    endpoint: str | None = None,
    instance_id: str | None = None,
    export_timeout: float | None = None,
) -> LoggerProvider | None:
    if not endpoint:
        return None

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

    provider = LoggerProvider(resource=build_resource(service_name, instance_id))
    provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs", timeout=export_timeout))
    )
    set_logger_provider(provider)
    return provider


def otlp_log_handler(provider: LoggerProvider) -> logging.Handler:
    from opentelemetry.instrumentation.logging.handler import LoggingHandler

    return LoggingHandler(logger_provider=provider)
