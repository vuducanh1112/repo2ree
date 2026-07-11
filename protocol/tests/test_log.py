from __future__ import annotations

import json
import logging
import sys

from repo2ree_protocol import log


def test_json_formatter_includes_trace_context(monkeypatch) -> None:
    monkeypatch.setattr(
        log,
        "current_trace_context",
        lambda: ("11111111111111111111111111111111", "2222222222222222"),
    )
    record = logging.LogRecord(
        name="repo2ree.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=10,
        msg="command %s",
        args=("failed",),
        exc_info=None,
    )

    payload = json.loads(log._JsonFormatter().format(record))

    assert payload["level"] == "WARNING"
    assert payload["logger"] == "repo2ree.test"
    assert payload["message"] == "command failed"
    assert payload["trace_id"] == "11111111111111111111111111111111"
    assert payload["span_id"] == "2222222222222222"
    assert payload["ts"].endswith("+00:00")


def test_json_formatter_omits_trace_context_when_no_span(monkeypatch) -> None:
    monkeypatch.setattr(log, "current_trace_context", lambda: None)
    record = logging.LogRecord(
        name="repo2ree.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )

    payload = json.loads(log._JsonFormatter().format(record))

    assert "trace_id" not in payload
    assert "span_id" not in payload


def test_json_formatter_includes_exception_text(monkeypatch) -> None:
    monkeypatch.setattr(log, "current_trace_context", lambda: None)
    try:
        raise ValueError("bad input")
    except ValueError:
        record = logging.getLogger("repo2ree.test").makeRecord(
            name="repo2ree.test",
            level=logging.ERROR,
            fn=__file__,
            lno=10,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
            func=None,
            extra=None,
        )

    payload = json.loads(log._JsonFormatter().format(record))

    assert "ValueError: bad input" in payload["exc"]


def test_configure_logging_sets_json_handler_and_env_level(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    log.configure_logging(structured=True)

    assert logging.root.level == logging.DEBUG
    assert len(logging.root.handlers) == 1
    handler = logging.root.handlers[0]
    assert isinstance(handler.formatter, log._JsonFormatter)


def test_configure_logging_falls_back_to_info_for_unknown_level(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "not-a-level")

    log.configure_logging()

    assert logging.root.level == logging.INFO
    assert len(logging.root.handlers) == 1
    handler = logging.root.handlers[0]
    assert isinstance(handler.formatter, logging.Formatter)
    assert not isinstance(handler.formatter, log._JsonFormatter)


class _CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_configure_logging_attaches_otlp_handler_but_filters_otel_internals() -> None:
    otlp = _CapturingHandler()

    log.configure_logging(otlp_handler=otlp)

    assert otlp in logging.root.handlers
    logging.getLogger("repo2ree.something").info("app record")
    logging.getLogger("opentelemetry.exporter").warning("export failed")
    assert [r.getMessage() for r in otlp.records] == ["app record"]


def test_emit_run_log_exports_with_attributes_and_mapped_level() -> None:
    otlp = _CapturingHandler()
    log.configure_run_log_export(otlp)

    log.emit_run_log("ree-1", "run-1", "stderr", "warn", "boom")
    log.emit_run_log("ree-1", "run-1", "stdout", "unknown-level", "hello")

    warn, info = otlp.records
    assert warn.levelno == logging.WARNING
    assert warn.getMessage() == "boom"
    assert getattr(warn, "repo2ree.ree_id") == "ree-1"
    assert getattr(warn, "repo2ree.run_id") == "run-1"
    assert getattr(warn, "repo2ree.stream") == "stderr"
    assert info.levelno == logging.INFO


def test_run_log_logger_does_not_propagate_to_root() -> None:
    root_handler = _CapturingHandler()
    log.configure_logging()
    logging.root.addHandler(root_handler)
    log.configure_run_log_export(_CapturingHandler())

    log.emit_run_log("ree-1", "run-1", "stdout", "info", "chatty build line")

    assert root_handler.records == []


def test_emit_run_log_without_export_is_a_noop() -> None:
    log.configure_run_log_export(None)

    log.emit_run_log("ree-1", "run-1", "stdout", "info", "dropped")  # must not raise or print


def test_setup_logs_is_noop_without_endpoint() -> None:
    from repo2ree_protocol.tracing import setup_logs

    assert setup_logs("repo2ree-test") is None
