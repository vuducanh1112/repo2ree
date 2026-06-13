"""Shared trace-artifact handling for both API test tiers.

Each tier's conftest points ``TRACE_FILE`` at its own
``test-results/<tier>/traces.ndjson`` and clears it at session start. The
file span exporter uses a ``SimpleSpanProcessor`` (see
``repo2ree_protocol.tracing.setup_tracing``), so every span is appended
synchronously the instant it ends. That lets us carve a per-test view out of
the session file by byte offset — no change to the tracing code, and the
session file stays intact as the whole-run record.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest


def _trace_file() -> Path | None:
    value = os.environ.get("TRACE_FILE")
    return Path(value) if value else None


def _slug(nodeid: str) -> str:
    """``test_runs_api.py::test_x[case]`` -> ``test_runs_api.py__test_x_case``."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nodeid).strip("_")


@pytest.fixture(autouse=True)
def per_test_traces(request: pytest.FixtureRequest) -> Iterator[None]:
    """Split the spans a single test produced into ``by-test/<nodeid>.ndjson``.

    Records the trace file's size before the test and copies everything
    appended during it into a per-test file. Tests that emit no spans (no app
    boot) just produce no slice. Caveat: a background run worker's span can end
    just after the test returns and land in the next test's slice — the
    session-wide ``traces.ndjson`` remains the source of truth.
    """
    path = _trace_file()
    start = path.stat().st_size if path and path.exists() else 0

    yield

    path = _trace_file()
    if path is None or not path.exists():
        return
    with path.open("rb") as fh:
        fh.seek(start)
        chunk = fh.read()
    if not chunk.strip():
        return
    out = path.parent / "by-test" / f"{_slug(request.node.nodeid)}.ndjson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(chunk)
