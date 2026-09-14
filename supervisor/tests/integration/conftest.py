"""Trace capture for the real-workbench e2e tier.

The API tiers get their tracer provider from the app's lifespan. This tier has
no app — it drives ``WorkbenchManager`` directly — so nothing would bootstrap
tracing and the run would leave no span record at all. That is the gap this
closes: the one suite that exercises a real ``build_runtime`` inside a real
container was also the one producing nothing to read afterwards.

The trace file lands beside the ``dockerd.log`` / ``workbench.log`` this tier
already keeps, under ``test-artifacts/python/services/supervisor-e2e/``.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from test_support.artifacts import service_dir

from repo2ree_protocol.tracing import setup_tracing

TRACE_DIR = service_dir("supervisor-e2e")

# Set at import, before any test module builds a manager or a tracer: the file
# exporter reads this when the provider is created, and the provider is global
# and set-once.
if "TRACE_FILE" not in os.environ:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    _trace_path = TRACE_DIR / "traces.ndjson"
    _trace_path.unlink(missing_ok=True)
    os.environ["TRACE_FILE"] = str(_trace_path)


@pytest.fixture(scope="session", autouse=True)
def _tracing() -> Iterator[None]:
    """Bootstrap the process-global tracer provider for the whole session.

    Session-scoped because OpenTelemetry allows the provider to be set once per
    process; a per-test provider would silently keep only the first one's spans.
    """
    provider = setup_tracing("repo2ree-supervisor", console_fallback=True)
    yield
    if provider is not None:
        provider.shutdown()
