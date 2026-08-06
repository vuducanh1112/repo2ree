"""Trace capture for the real-workbench e2e tier.

The API tiers get their tracer provider from the app's lifespan. This tier has
no app — it drives ``WorkbenchManager`` directly — so nothing would bootstrap
tracing and the run would leave no span record at all. That is the gap this
closes: the one suite that exercises a real ``build_runtime`` inside a real
container was also the one producing nothing to read afterwards.

The trace file lands beside the ``dockerd.log`` / ``workbench.log`` this tier
already keeps, under ``test-artifacts/traces/supervisor-e2e/``.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol.tracing import setup_tracing

TRACE_DIR = Path(__file__).resolve().parents[3] / "test-artifacts" / "traces" / "supervisor-e2e"

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


def _slug(nodeid: str) -> str:
    """``test_x.py::test_y[case]`` -> ``test_x.py__test_y_case``."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nodeid).strip("_")


@pytest.fixture(autouse=True)
def per_test_traces(request: pytest.FixtureRequest) -> Iterator[None]:
    """Carve the spans one test produced into ``by-test/<nodeid>.ndjson``.

    Same byte-offset trick the API tiers use: the file exporter appends
    synchronously through a ``SimpleSpanProcessor``, so everything written
    between these two points belongs to this test. The session file stays the
    whole-run record.
    """
    path = Path(os.environ["TRACE_FILE"])
    start = path.stat().st_size if path.exists() else 0

    yield

    if not path.exists():
        return
    with path.open("rb") as handle:
        handle.seek(start)
        chunk = handle.read()
    if not chunk.strip():
        return
    out = path.parent / "by-test" / f"{_slug(request.node.nodeid)}.ndjson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(chunk)
