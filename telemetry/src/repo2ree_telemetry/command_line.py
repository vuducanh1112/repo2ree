from __future__ import annotations

import os
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import TextIO

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from repo2ree_protocol.result import ActionResult
from repo2ree_telemetry.bootstrap import TRACE_FILE_ENV, get_tracer, otlp_log_handler, setup_logs, setup_tracing
from repo2ree_telemetry.log import configure_logging
from repo2ree_telemetry.relay import setup_relay_tracing
from repo2ree_telemetry.spans import (
    record_command_status,
    record_exit_code,
    record_failure,
    record_result_evidence,
    remote_context,
)

TRACE_RELAY_ENV = "TRACE_RELAY"
TRACEPARENT_ENV = "TRACEPARENT"
OTLP_ENDPOINT_ENV = "OTLP_ENDPOINT"

_EXPORT_TIMEOUT = 2.0
_PROGRAM = "ree"
_ATTR_COMMAND = "repo2ree.cli.command"

tracer = get_tracer(__name__)


def setup_command_line_telemetry(service_name: str, relay: TextIO) -> Callable[[], None]:
    if os.environ.get(TRACE_RELAY_ENV):
        configure_logging()
        setup_relay_tracing(service_name, relay)
        return lambda: None
    endpoint = os.environ.get(OTLP_ENDPOINT_ENV) or None
    logger_provider = setup_logs(service_name, endpoint=endpoint, export_timeout=_EXPORT_TIMEOUT)
    configure_logging(otlp_handler=otlp_log_handler(logger_provider) if logger_provider else None)
    tracer_provider = setup_tracing(
        service_name,
        endpoint=endpoint,
        console_fallback=bool(os.environ.get(TRACE_FILE_ENV)),
        export_timeout=_EXPORT_TIMEOUT,
    )

    def shutdown() -> None:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()

    return shutdown


@contextmanager
def invocation_span() -> Iterator[None]:
    with tracer.start_as_current_span(
        _PROGRAM,
        context=remote_context(os.environ.get(TRACEPARENT_ENV)),
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield
        except SystemExit as exit_:
            code = exit_.code if isinstance(exit_.code, int) else (0 if exit_.code is None else 1)
            record_exit_code(span, code)
            if code != 0:
                span.set_status(StatusCode.ERROR, f"exit {code}")
            raise
        except BaseException as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, type(exc).__name__)
            raise


def name_invocation(words: Sequence[str]) -> None:
    span = trace.get_current_span()
    command = " ".join(words)
    span.update_name(f"{_PROGRAM} {command}")
    span.set_attribute(_ATTR_COMMAND, command)


def record_invocation_result(result: ActionResult) -> None:
    span = trace.get_current_span()
    record_failure(span, result.failure)
    record_command_status(span, result.status)
    record_result_evidence(span, result)
