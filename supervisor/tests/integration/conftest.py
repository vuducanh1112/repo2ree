from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from repo2ree_telemetry.bootstrap import setup_tracing
from repo2ree_testbed.artifacts import service_dir

TRACE_DIR = service_dir("supervisor-e2e")

if "TRACE_FILE" not in os.environ:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    _trace_path = TRACE_DIR / "traces.ndjson"
    _trace_path.unlink(missing_ok=True)
    os.environ["TRACE_FILE"] = str(_trace_path)


@pytest.fixture(scope="session", autouse=True)
def _tracing() -> Iterator[None]:
    provider = setup_tracing("repo2ree-supervisor", console_fallback=True)
    yield
    if provider is not None:
        provider.shutdown()
