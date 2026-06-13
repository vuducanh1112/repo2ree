"""Fixtures for the real-component API integration tier.

These tests run the actual FastAPI app over HTTP (via ``TestClient``) against
the real module-level ``WorkbenchManager`` — real ``docker run`` /
``docker exec`` transport, real workbench containers, real ``/ree`` volumes.
Nothing is mocked; like the supervisor e2e, the suite skips (never fakes)
when Docker or the workbench image is absent.

Host-side state (upload staging, reviews, the workbench registry) is
redirected into a throwaway directory via env vars *before* the app module —
and with it the workbench-manager singleton — is imported, so a developer's
``.env`` or live registry can't leak into the tests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

TEST_RESULTS_DIR = Path(__file__).resolve().parents[3] / "test-results" / "api-integration"

# Env vars take precedence over .env in pydantic-settings, and the settings
# (plus the registry singleton built from them) are read at import time — so
# this must run before any repo2ree_api import below.
_state_dir = Path(tempfile.mkdtemp(prefix="repo2ree-api-itest-"))
os.environ["UPLOAD_STAGING_DIR"] = str(_state_dir / "upload-staging")
os.environ["REVIEWS_STORAGE_DIR"] = str(_state_dir / "reviews")
os.environ["WORKBENCH_REGISTRY_FILE"] = str(_state_dir / "workbench-registry.json")
# OpenTelemetry's set_tracer_provider is honored once per process, so two API
# tiers in one pytest run share a single provider baked to whichever tier booted
# first — the other's spans silently flow to the wrong file. make runs the tiers
# as separate processes; this turns the unsafe `pytest api/tests` path into a
# loud, explained failure instead of wrong traces.
_claimed = os.environ.get("_REPO2REE_TRACE_TIER")
if _claimed and _claimed != "api-integration":
    raise RuntimeError(
        f"Both {_claimed} and api-integration tiers loaded in one pytest process; their spans "
        "collide on OpenTelemetry's set-once global provider. Run them separately: "
        "`make api-unit-tests` / `make api-integration-tests`, or `pytest api/tests/unit` "
        "and `pytest api/tests/integration`."
    )
os.environ["_REPO2REE_TRACE_TIER"] = "api-integration"

# Unless a collector or another file was chosen, every span the suite produces
# — API request/command spans and the relayed executor spans alike — appends
# to one inspectable NDJSON file. Start each run fresh (the exporter appends),
# clearing the per-test slices too; only touch the path we own.
if "TRACE_FILE" not in os.environ:
    _trace_file = TEST_RESULTS_DIR / "traces.ndjson"
    os.environ["TRACE_FILE"] = str(_trace_file)
    _trace_file.parent.mkdir(parents=True, exist_ok=True)
    _trace_file.unlink(missing_ok=True)
    shutil.rmtree(TEST_RESULTS_DIR / "by-test", ignore_errors=True)

from fastapi.testclient import TestClient  # noqa: E402

from repo2ree_api.main import app  # noqa: E402

# ================================================
# Fixtures
# ================================================


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """The real app over HTTP, with the lifespan running.

    Session-scoped because the lifespan bootstraps the process-global tracer
    provider, which OpenTelemetry only allows to be set once: one lifespan per
    test session keeps every span on the live provider. Spans go to the
    TRACE_FILE set above (or to OTLP_ENDPOINT when configured), so every run
    leaves an inspectable trace record.
    """
    with TestClient(app) as client:
        yield client


@pytest.fixture
def ree(client: TestClient, request: pytest.FixtureRequest) -> Iterator[dict[str, Any]]:
    """A real REE backed by a freshly provisioned workbench container.

    Teardown snapshots the container's logs into ``test-results/`` for
    post-run inspection, then deletes the REE (container + volumes) through
    the API. The delete is idempotent here: a test that already deleted its
    REE just gets a 404 back.
    """
    resp = client.post("/api/v1/rees", json={"sourceMode": "upload", "name": "api-itest"})
    assert resp.status_code == 200, resp.text
    workspace = resp.json()
    ree_id = workspace["reeId"]
    try:
        yield workspace
    finally:
        _dump_workbench_logs(ree_id, request.node.name)
        client.delete(f"/api/v1/rees/{ree_id}")


# ================================================
# Helpers
# ================================================


def _dump_workbench_logs(ree_id: str, test_name: str) -> None:
    """Snapshot the workbench's logs before it is torn down.

    ``workbench.log`` is the container's entrypoint output; ``dockerd.log`` is
    the in-container Docker daemon's log (the entrypoint redirects it to
    ``/var/log/dockerd.log``), which is where runtime-build failures surface.
    """
    container_name = f"repo2ree-wb-{ree_id}"
    out_dir = TEST_RESULTS_DIR / test_name
    out_dir.mkdir(parents=True, exist_ok=True)

    entrypoint = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
    (out_dir / "workbench.log").write_text(entrypoint.stdout + entrypoint.stderr)

    dockerd = subprocess.run(
        ["docker", "exec", container_name, "cat", "/var/log/dockerd.log"],
        capture_output=True,
        text=True,
    )
    (out_dir / "dockerd.log").write_text(dockerd.stdout + dockerd.stderr)
