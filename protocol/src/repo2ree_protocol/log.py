"""Log-streaming contract and process-level logging configuration.

``LogSink`` is the streaming callback shared across the command boundary.
``configure_logging`` is the one-shot bootstrap called by each process
entry point (api lifespan, executor main).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime

from repo2ree_protocol.tracing import current_trace_context

LogSink = Callable[[str, str, str], None]


# ================================================
# Formatters
# ================================================


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, str] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        # Stamp the active trace so the collector can pivot log <-> trace.
        trace_ctx = current_trace_context()
        if trace_ctx is not None:
            obj["trace_id"], obj["span_id"] = trace_ctx
        return json.dumps(obj)


# ================================================
# Public API
# ================================================


def configure_logging(*, structured: bool = False, otlp_handler: logging.Handler | None = None) -> None:
    """Configure root logger once.

    Emits JSON when ``structured`` is set (for a log aggregator), plain text
    otherwise. The caller owns that decision — the API turns it on when a
    collector is configured; the executor leaves it off, since its meaningful
    logs travel as NDJSON through the LogSink relay, not this root handler.
    Log level defaults to INFO; override with the LOG_LEVEL env var.

    ``otlp_handler`` (from ``tracing.otlp_log_handler``) additionally ships
    every record to the collector, trace-correlated. The OTel SDK's own
    loggers are excluded from it: an exporter that logs its own failures
    through the handler that exports would feed itself.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if structured:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.root.handlers = [handler]
    if otlp_handler is not None:
        otlp_handler.addFilter(_not_otel_internals)
        logging.root.addHandler(otlp_handler)
    logging.root.setLevel(level)


def _not_otel_internals(record: logging.LogRecord) -> bool:
    return not record.name.startswith("opentelemetry")


# ================================================
# Run-log export (the LogSink stream)
# ================================================

# Dedicated, non-propagating logger for run-stream lines (LogSink frames
# relayed from the workbench). Kept off the root logger so a chatty build
# does not spray thousands of lines onto the process's stdout — its only
# destination is the collector, wired by ``configure_run_log_export``.
_RUN_LOG_LOGGER = "repo2ree.run"

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_run_log_export(otlp_handler: logging.Handler | None) -> None:
    """Route ``emit_run_log`` lines to the collector (or nowhere when None)."""
    run_logger = logging.getLogger(_RUN_LOG_LOGGER)
    run_logger.handlers = [otlp_handler] if otlp_handler is not None else [logging.NullHandler()]
    run_logger.propagate = False
    run_logger.setLevel(logging.DEBUG)


def emit_run_log(ree_id: str, run_id: str, stream: str, level: str, message: str) -> None:
    """Export one run-stream log line, correlated to the active span.

    Called wherever the run's LogSink lands host-side (the run registry), so
    the workbench-internal stream becomes clickable from the trace that
    dispatched it and survives the container. ``stream`` (stdout/stderr/
    system) travels as an attribute, not a severity, so a build that merely
    writes to stderr does not read as failing.
    """
    logging.getLogger(_RUN_LOG_LOGGER).log(
        _LEVELS.get(level, logging.INFO),
        "%s",
        message,
        extra={
            "repo2ree.ree_id": ree_id,
            "repo2ree.run_id": run_id,
            "repo2ree.stream": stream,
        },
    )
