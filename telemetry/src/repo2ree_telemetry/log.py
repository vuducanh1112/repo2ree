from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

from repo2ree_telemetry.spans import current_trace_context


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
        trace_ctx = current_trace_context()
        if trace_ctx is not None:
            obj["trace_id"], obj["span_id"] = trace_ctx
        return json.dumps(obj)


def configure_logging(*, structured: bool = False, otlp_handler: logging.Handler | None = None) -> None:
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


_RUN_LOG_LOGGER = "repo2ree.run"

_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def configure_run_log_export(otlp_handler: logging.Handler | None) -> None:
    run_logger = logging.getLogger(_RUN_LOG_LOGGER)
    run_logger.handlers = [otlp_handler] if otlp_handler is not None else [logging.NullHandler()]
    run_logger.propagate = False
    run_logger.setLevel(logging.DEBUG)


def emit_run_log(ree_id: str, run_id: str, stream: str, level: str, message: str) -> None:
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
