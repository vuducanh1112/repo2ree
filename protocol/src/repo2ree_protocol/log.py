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

LogSink = Callable[[str, str, str], None]


# ================================================
# Formatters
# ================================================


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.formatMessage(record),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj)


# ================================================
# Public API
# ================================================


def configure_logging(*, structured: bool = False) -> None:
    """Configure root logger once.

    Emits JSON when ``structured`` is set (for a log aggregator), plain text
    otherwise. The caller owns that decision — the API turns it on when a
    collector is configured; the executor leaves it off, since its meaningful
    logs travel as NDJSON through the LogSink relay, not this root handler.
    Log level defaults to INFO; override with the LOG_LEVEL env var.
    """
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if structured:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
