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
