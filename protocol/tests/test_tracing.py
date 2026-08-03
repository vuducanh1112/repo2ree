from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest
from opentelemetry import context
from opentelemetry import metrics as metrics_api
from opentelemetry import trace as trace_api
from opentelemetry.proto.common.v1.common_pb2 import AnyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span as PbSpan
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    Status,
    StatusCode,
    TraceFlags,
    set_span_in_context,
)

from repo2ree_protocol import tracing
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    ExecSpanAttrs,
    ScriptSpanAttrs,
    WorkbenchSpanAttrs,
    _anyvalue,
    _BackgroundSpanForwarder,
    _build_resource,
    _console_span_sink,
    _format_relayed_span,
    _RelaySpanExporter,
    _SpanFactCarrier,
    attach_remote_context,
    build_span_sink,
    command_metric_attrs,
    current_trace_context,
    current_traceparent,
    detach_context,
    forward_relayed_spans,
    otlp_log_handler,
    record_command_status,
    record_current_span_facts,
    record_exec_outcome,
    record_exit_code,
    record_ree_id,
    record_span_facts,
    remote_context,
    setup_logs,
    setup_metrics,
    setup_relay_tracing,
    setup_tracing,
)


@dataclass
class _FakeSpan:
    attributes: dict[str, object] = field(default_factory=dict)
    status: Status | None = None

    def set_attribute(self, key: str, value: object) -> None:
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


def test_record_span_facts_flattens_and_shapes_values() -> None:
    span = _FakeSpan()

    record_span_facts(
        cast(Span, span),
        {
            "origin_url": "https://example.com/repo.git",
            "refetch": False,
            "exit_code": 0,
            "skipped": None,
            "upload_token": "secret",
            "content": "x" * 1000,
            "receipt": {"snapshot_digest": "sha256:abc", "changed_paths": ["a", "b"]},
        },
        namespace="arg",
    )

    assert span.attributes == {
        "repo2ree.arg.origin_url": "https://example.com/repo.git",
        "repo2ree.arg.refetch": False,
        "repo2ree.arg.exit_code": 0,
        "repo2ree.arg.content.size": 1000,
        "repo2ree.arg.receipt.snapshot_digest": "sha256:abc",
        "repo2ree.arg.receipt.changed_paths.count": 2,
    }


def test_record_span_facts_truncates_long_strings_and_caps_attribute_count() -> None:
    span = _FakeSpan()

    record_span_facts(cast(Span, span), {"long": "y" * 500})
    long_value = cast(str, span.attributes["repo2ree.long"])
    assert len(long_value) == 256
    assert long_value.endswith("…")

    crowded = _FakeSpan()
    record_span_facts(cast(Span, crowded), {f"k{i}": i for i in range(100)})
    assert len(crowded.attributes) == 64


def test_typed_carriers_own_the_key_vocabulary() -> None:
    span = _FakeSpan()
    protocol_span = cast(Span, span)

    ExecSpanAttrs(argv="sh build.sh", cwd="/ree/workspace").apply(protocol_span)
    ScriptSpanAttrs(path="build.sh").apply(protocol_span)
    WorkbenchSpanAttrs(container="wb-1", image="repo2ree:dev", agent_id="agent-1").apply(protocol_span)
    record_exit_code(protocol_span, 0)

    assert span.attributes == {
        "repo2ree.exec.argv": "sh build.sh",
        "repo2ree.exec.cwd": "/ree/workspace",
        "repo2ree.script.path": "build.sh",
        "repo2ree.workbench.container": "wb-1",
        "repo2ree.workbench.image": "repo2ree:dev",
        "repo2ree.agent_id": "agent-1",
        "repo2ree.exit_code": 0,
    }


def test_build_resource_records_instance_id_only_when_given() -> None:
    plain = _build_resource("repo2ree-agent")
    assert plain.attributes["service.name"] == "repo2ree-agent"
    assert "service.instance.id" not in plain.attributes

    instanced = _build_resource("repo2ree-agent", "host-a1b2c3")
    assert instanced.attributes["service.instance.id"] == "host-a1b2c3"


def test_build_resource_carries_deploy_identity_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERVICE_VERSION", raising=False)
    monkeypatch.delenv("DEPLOY_ENV", raising=False)
    local = _build_resource("repo2ree-api")
    # Unset in local dev, so a dashboard never has to filter on an empty slice.
    assert "service.version" not in local.attributes
    assert "deployment.environment" not in local.attributes

    monkeypatch.setenv("SERVICE_VERSION", "1.4.2")
    monkeypatch.setenv("DEPLOY_ENV", "staging")
    deployed = _build_resource("repo2ree-api")
    assert deployed.attributes["service.version"] == "1.4.2"
    assert deployed.attributes["deployment.environment"] == "staging"


def test_otlp_headers_from_env_parses_pairs_and_ignores_junk(monkeypatch) -> None:
    from repo2ree_protocol.tracing import _otlp_headers_from_env

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_HEADERS", raising=False)
    assert _otlp_headers_from_env() == {}

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=key-123, x-scope=dev,malformed")
    assert _otlp_headers_from_env() == {"authorization": "key-123", "x-scope": "dev"}

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    assert _otlp_headers_from_env() == {}


def test_record_exit_code_skips_none() -> None:
    span = _FakeSpan()

    record_exit_code(cast(Span, span), None)

    assert span.attributes == {}


def test_record_exec_outcome_success_records_sizes_but_no_tails() -> None:
    span = _FakeSpan()

    record_exec_outcome(cast(Span, span), exit_code=0, canceled=False, stdout="ok\n", stderr="")

    assert span.attributes == {
        "repo2ree.exit_code": 0,
        "repo2ree.canceled": False,
        "repo2ree.exec.stdout_chars": 3,
        "repo2ree.exec.stderr_chars": 0,
    }
    assert span.status is None


def test_record_exec_outcome_failure_records_output_tails_and_error_status() -> None:
    span = _FakeSpan()

    record_exec_outcome(
        cast(Span, span),
        exit_code=7,
        canceled=False,
        stdout="building...",
        stderr="e" * 5000,
    )

    assert span.attributes["repo2ree.exec.stdout_tail"] == "building..."
    stderr_tail = cast(str, span.attributes["repo2ree.exec.stderr_tail"])
    assert len(stderr_tail) == 2048
    assert span.status is not None
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "exit 7"


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


# ================================================
# Active-span helpers
# ================================================


def test_record_current_span_facts_targets_the_active_span() -> None:
    # A NonRecordingSpan is what an unsampled or absent trace leaves current;
    # facts aimed at it must go nowhere rather than raise.
    token = _attach_span(0x33333333333333333333333333333333, 0x4444444444444444)
    try:
        record_current_span_facts({"operation": "build_runtime"})
    finally:
        context.detach(token)  # type: ignore[arg-type]

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer(__name__).start_as_current_span("run"):
        record_current_span_facts({"operation": "build_runtime"}, namespace="arg")
    provider.shutdown()

    (recorded,) = exporter.get_finished_spans()
    assert recorded.attributes is not None
    assert recorded.attributes["repo2ree.arg.operation"] == "build_runtime"


def test_current_trace_context_is_none_without_a_valid_span() -> None:
    assert current_trace_context() is None
    assert current_traceparent() is None


def test_remote_context_parents_a_span_to_the_caller() -> None:
    assert remote_context(None) is None
    assert remote_context("") is None

    traceparent = "00-cccccccccccccccccccccccccccccccc-dddddddddddddddd-01"
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer(__name__).start_as_current_span("child", context=remote_context(traceparent)):
        pass
    provider.shutdown()

    (child,) = exporter.get_finished_spans()
    assert f"{child.context.trace_id:032x}" == "cccccccccccccccccccccccccccccccc"
    assert child.parent is not None
    assert f"{child.parent.span_id:016x}" == "dddddddddddddddd"


def test_span_fact_carrier_base_declares_no_vocabulary_of_its_own() -> None:
    with pytest.raises(NotImplementedError):
        _SpanFactCarrier().apply(cast(Span, _FakeSpan()))


# ================================================
# Bootstrap
# ================================================


@pytest.fixture
def _no_global_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the bootstrap functions from claiming this process's globals.

    OpenTelemetry's ``set_*_provider`` calls are set-once per process, and this
    tier shares a process with the core and api unit tiers under the coverage
    targets. Registering a real provider here would silently become *their*
    provider too, so the registration is captured instead of performed.
    """
    # Patched on the OpenTelemetry modules themselves — the same module objects
    # tracing.py holds its references to.
    monkeypatch.setattr(trace_api, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(metrics_api, "set_meter_provider", lambda provider: None)


@pytest.fixture
def _stub_otlp_exporters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the OTLP/HTTP exporters for in-memory ones.

    The bootstrap functions import their exporters at call time, so patching
    the exporter modules reaches them. What is under test is the wiring —
    resource, processors, the duration view — not OTel's network egress, and a
    real exporter would have this suite POSTing to a dead endpoint on shutdown.
    """
    import opentelemetry.exporter.otlp.proto.http._log_exporter as log_exporter_module
    import opentelemetry.exporter.otlp.proto.http.metric_exporter as metric_exporter_module
    import opentelemetry.exporter.otlp.proto.http.trace_exporter as trace_exporter_module
    import opentelemetry.sdk.metrics.export as metrics_export_module

    monkeypatch.setattr(trace_exporter_module, "OTLPSpanExporter", lambda endpoint: InMemorySpanExporter())
    monkeypatch.setattr(log_exporter_module, "OTLPLogExporter", lambda endpoint: InMemoryLogRecordExporter())
    monkeypatch.setattr(metric_exporter_module, "OTLPMetricExporter", lambda endpoint: None)
    # The reader owns the export cadence; an in-memory one collects on demand
    # and starts no periodic thread.
    monkeypatch.setattr(metrics_export_module, "PeriodicExportingMetricReader", lambda exporter: InMemoryMetricReader())


def test_setup_tracing_is_a_noop_without_an_endpoint_or_fallback() -> None:
    assert setup_tracing("repo2ree-exec") is None


@pytest.mark.usefixtures("_no_global_providers", "_stub_otlp_exporters")
def test_setup_tracing_exports_to_the_collector_when_given_an_endpoint() -> None:
    provider = setup_tracing("repo2ree-api", endpoint="http://collector:4318")

    assert provider is not None
    assert provider.resource.attributes["service.name"] == "repo2ree-api"
    provider.shutdown()


@pytest.mark.usefixtures("_no_global_providers")
def test_setup_tracing_console_fallback_appends_spans_to_the_trace_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_file = tmp_path / "traces.ndjson"
    monkeypatch.setenv("TRACE_FILE", str(trace_file))

    provider = setup_tracing("repo2ree-api", console_fallback=True)
    assert provider is not None
    with provider.get_tracer(__name__).start_as_current_span("workbench.exec"):
        pass
    provider.shutdown()

    lines = trace_file.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["name"] for line in lines] == ["workbench.exec"]


@pytest.mark.usefixtures("_no_global_providers")
def test_setup_tracing_console_fallback_without_a_trace_file_writes_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TRACE_FILE", raising=False)

    provider = setup_tracing("repo2ree-api", console_fallback=True)
    assert provider is not None
    with provider.get_tracer(__name__).start_as_current_span("workbench.exec"):
        pass
    provider.shutdown()

    assert "workbench.exec" in capsys.readouterr().out


def test_setup_metrics_is_a_noop_without_an_endpoint() -> None:
    assert setup_metrics("repo2ree-exec") is None


@pytest.mark.usefixtures("_no_global_providers", "_stub_otlp_exporters")
def test_setup_metrics_builds_a_provider_carrying_the_service_identity() -> None:
    provider = setup_metrics("repo2ree-agent", endpoint="http://collector:4318", instance_id="agent-a1")

    assert provider is not None
    assert provider._sdk_config.resource.attributes["service.instance.id"] == "agent-a1"
    provider.shutdown()


def test_setup_logs_is_a_noop_without_an_endpoint() -> None:
    assert setup_logs("repo2ree-exec") is None


@pytest.mark.usefixtures("_stub_otlp_exporters")
def test_setup_logs_returns_a_provider_backing_a_logging_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    import opentelemetry._logs as logs_api

    monkeypatch.setattr(logs_api, "set_logger_provider", lambda provider: None)

    provider = setup_logs("repo2ree-api", endpoint="http://collector:4318")
    assert provider is not None
    assert isinstance(otlp_log_handler(provider), logging.Handler)
    provider.shutdown()


# ================================================
# Executor span relay
# ================================================


def _relayed_payload(span_name: str = "command.build_runtime") -> str:
    """Produce one real relay payload the way the executor does.

    Drives ``_RelaySpanExporter`` with a genuine ended span, so everything
    downstream (the forwarder, the console sink) is tested against bytes the
    executor would actually emit rather than a hand-built fixture.
    """
    stream = io.StringIO()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_RelaySpanExporter(stream)))
    with provider.get_tracer(__name__).start_as_current_span(span_name):
        pass
    provider.shutdown()

    event = json.loads(stream.getvalue().strip())
    assert event["type"] == "span"
    payload = event["payload"]
    assert isinstance(payload, str)
    return payload


def test_relay_exporter_writes_one_ndjson_span_event() -> None:
    payload = _relayed_payload()

    # Base64 OTLP protobuf: the supervisor relays the bytes without decoding
    # them, so the only contract here is that they round-trip.
    assert base64.b64decode(payload)


def test_setup_relay_tracing_streams_the_executors_spans_for_relay(monkeypatch: pytest.MonkeyPatch) -> None:
    registered: list[TracerProvider] = []
    monkeypatch.setattr(trace_api, "set_tracer_provider", registered.append)

    stream = io.StringIO()
    setup_relay_tracing("repo2ree-exec", stream)

    # Registered globally in the executor process; here it is captured, so the
    # span has to be started on the provider directly.
    (provider,) = registered
    with provider.get_tracer(__name__).start_as_current_span("command.build_runtime"):
        pass
    provider.shutdown()

    # Emitted per span as it ends, not batched: the executor's process exits and
    # closes the stream the moment its command is done.
    event = json.loads(stream.getvalue().strip())
    assert event["type"] == "span"
    assert base64.b64decode(event["payload"])


def test_relay_exporter_flush_and_shutdown_are_inert() -> None:
    exporter = _RelaySpanExporter(io.StringIO())
    assert exporter.force_flush() is True
    # Nothing to tear down: the stream belongs to the executor, not the exporter.
    exporter.shutdown()


def test_forward_relayed_spans_posts_each_payload_with_configured_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    posted: list[dict[str, object]] = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

    def _post(url: str, data: bytes, headers: dict[str, str], timeout: int) -> _Response:
        posted.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        return _Response()

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "authorization=key-123")

    payload = _relayed_payload()
    forward_relayed_spans([payload], "http://collector:4318")

    assert len(posted) == 1
    assert posted[0]["url"] == "http://collector:4318/v1/traces"
    assert posted[0]["data"] == base64.b64decode(payload)
    headers = cast(dict[str, str], posted[0]["headers"])
    assert headers["Content-Type"] == "application/x-protobuf"
    assert headers["authorization"] == "key-123"


def test_forward_relayed_spans_swallows_post_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def _post(url: str, data: bytes, headers: dict[str, str], timeout: int) -> None:
        raise requests.RequestException("collector down")

    monkeypatch.setattr(requests, "post", _post)

    # Span egress must never break the command flow it rode in on.
    forward_relayed_spans([_relayed_payload()], "http://collector:4318")


def test_forward_relayed_spans_skips_the_network_when_there_is_nothing_to_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import requests

    def _unreachable(*args: object, **kwargs: object) -> None:
        pytest.fail("an empty payload list must not reach the network")

    monkeypatch.setattr(requests, "post", _unreachable)
    forward_relayed_spans([], "http://collector:4318")


def test_background_forwarder_drains_submissions_off_the_callers_thread() -> None:
    forwarded: list[list[str]] = []
    seen = threading.Event()

    def _forward(payloads: list[str]) -> None:
        forwarded.append(payloads)
        seen.set()

    forwarder = _BackgroundSpanForwarder(_forward)
    forwarder.submit([])  # nothing to do, and nothing enqueued
    forwarder.submit(["payload-a"])

    assert seen.wait(timeout=5.0)
    assert forwarded == [["payload-a"]]


def test_background_forwarder_survives_a_failing_sink() -> None:
    attempts = threading.Semaphore(0)

    def _forward(payloads: list[str]) -> None:
        attempts.release()
        raise RuntimeError("collector down")

    forwarder = _BackgroundSpanForwarder(_forward)
    forwarder.submit(["first"])
    assert attempts.acquire(timeout=5.0)
    # The worker must still be draining after one sink failure, not dead.
    forwarder.submit(["second"])
    assert attempts.acquire(timeout=5.0)


def test_background_forwarder_drops_rather_than_blocking_when_the_queue_is_full() -> None:
    release = threading.Event()
    started = threading.Event()

    def _forward(payloads: list[str]) -> None:
        started.set()
        release.wait(timeout=5.0)

    forwarder = _BackgroundSpanForwarder(_forward, max_queue=1)
    forwarder.submit(["in-flight"])
    assert started.wait(timeout=5.0)
    forwarder.submit(["queued"])
    # The queue holds one; this third submission is dropped instead of blocking
    # the manager's locked, latency-measured path.
    forwarder.submit(["dropped"])
    release.set()


def test_build_span_sink_returns_none_when_spans_have_nowhere_to_go() -> None:
    assert build_span_sink(None) is None
    assert build_span_sink("") is None


def test_build_span_sink_forwards_to_the_configured_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarded: list[tuple[list[str], str]] = []
    seen = threading.Event()

    def _forward(payloads: list[str], endpoint: str) -> None:
        forwarded.append((payloads, endpoint))
        seen.set()

    monkeypatch.setattr(tracing, "forward_relayed_spans", _forward)

    sink = build_span_sink("http://collector:4318")
    assert sink is not None
    sink(["payload-a"])

    assert seen.wait(timeout=5.0)
    assert forwarded == [(["payload-a"], "http://collector:4318")]


def test_build_span_sink_console_fallback_decodes_spans_locally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_file = tmp_path / "traces.ndjson"
    monkeypatch.setenv("TRACE_FILE", str(trace_file))

    sink = build_span_sink(None, console_fallback=True)
    assert sink is not None
    sink([_relayed_payload("command.generate_sbom")])

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not trace_file.exists():
        time.sleep(0.01)
    lines = trace_file.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["name"] for line in lines] == ["command.generate_sbom"]


def test_console_span_sink_writes_decoded_spans_to_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TRACE_FILE", raising=False)

    _console_span_sink([_relayed_payload("command.activation_test")])

    rendered = json.loads(capsys.readouterr().out.strip())
    assert rendered["name"] == "command.activation_test"
    assert rendered["parent_id"] is None


def test_console_span_sink_skips_a_malformed_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TRACE_FILE", raising=False)

    # A payload that survives base64 but is not OTLP protobuf: dropped with a
    # warning, and the good payload beside it still lands.
    _console_span_sink([base64.b64encode(b"not-a-protobuf").decode("ascii"), _relayed_payload("command.build_runtime")])

    names = [json.loads(line)["name"] for line in capsys.readouterr().out.splitlines()]
    assert names == ["command.build_runtime"]
