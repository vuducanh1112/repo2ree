"""Fixtures for the container-free API unit tier.

This tier runs the real FastAPI app over ``TestClient`` — real routers, real
exception handlers, real run registry, real upload staging — with no Docker
and no workbench containers, so it runs unconditionally on every machine.

The one seam is the workbench dispatch boundary: tests stage registry /
container state by patching ``lookup`` / ``is_registered`` on the real
module-level ``WorkbenchManager`` singleton. No workbench *behavior* is ever
faked — nothing fabricates an ``ActionResult`` to pretend a command ran.
Everything that crosses the boundary for real belongs to the Docker-gated
integration tier.

Host-side state (upload staging, the workbench registry) is redirected into a
throwaway directory via env vars *before* the app module —
and with it the workbench-manager singleton — is imported, so a developer's
``.env`` or live registry can't leak into the tests.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

TEST_RESULTS_DIR = Path(__file__).resolve().parents[3] / "test-artifacts" / "traces" / "api-unit"

# Env vars take precedence over .env in pydantic-settings, and the settings
# (plus the registry singleton built from them) are read at import time — so
# this must run before any repo2ree_api import below.
_state_dir = Path(tempfile.mkdtemp(prefix="repo2ree-api-utest-"))
os.environ["UPLOAD_STAGING_DIR"] = str(_state_dir / "upload-staging")
os.environ["WORKBENCH_REGISTRY_FILE"] = str(_state_dir / "workbench-registry.json")

# OpenTelemetry's set_tracer_provider is honored once per process, so two API
# tiers in one pytest run share a single provider baked to whichever tier booted
# first — the other's spans silently flow to the wrong file. make runs the tiers
# as separate processes; this turns the unsafe `pytest api/tests` path into a
# loud, explained failure instead of wrong traces.
_claimed = os.environ.get("_REPO2REE_TRACE_TIER")
if _claimed and _claimed != "api-unit":
    raise RuntimeError(
        f"Both {_claimed} and api-unit tiers loaded in one pytest process; their spans "
        "collide on OpenTelemetry's set-once global provider. Run them separately: "
        "`make api-unit-tests` / `make api-integration-tests`, or `pytest api/tests/unit` "
        "and `pytest api/tests/integration`."
    )
os.environ["_REPO2REE_TRACE_TIER"] = "api-unit"

# Start each run with a fresh trace file. The file span exporter opens in
# append mode, so without clearing, spans pile up across runs. Only clear the
# path we own — if TRACE_FILE was set externally (e.g. pointed at a shared
# file), leave it untouched. The per-test slices (api/tests/conftest.py) are
# cleared alongside it.
if "TRACE_FILE" not in os.environ:
    _trace_file = TEST_RESULTS_DIR / "traces.ndjson"
    os.environ["TRACE_FILE"] = str(_trace_file)
    _trace_file.parent.mkdir(parents=True, exist_ok=True)
    _trace_file.unlink(missing_ok=True)
    shutil.rmtree(TEST_RESULTS_DIR / "by-test", ignore_errors=True)

from fastapi.testclient import TestClient  # noqa: E402

from repo2ree_api.main import app  # noqa: E402
from repo2ree_api.workbench.deps import workbench_manager  # noqa: E402
from repo2ree_supervisor import WorkbenchHandle  # noqa: E402

# ================================================
# Fixtures
# ================================================


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """The real app over HTTP, with the lifespan running.

    Session-scoped because the lifespan bootstraps the process-global tracer
    provider, which OpenTelemetry only allows to be set once. Server
    exceptions are returned as responses (not re-raised) so tests can assert
    the 500 error envelope the way a client would see it.
    """
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def online_ree(monkeypatch: pytest.MonkeyPatch) -> WorkbenchHandle:
    """Stage one REE as registered-and-running on the real manager singleton.

    Patches ``lookup`` / ``is_registered`` so routes resolve a handle for this
    REE without a docker probe; every other ID falls through to the real
    (empty-registry) behavior. Anything that *dispatches* through the handle
    is out of scope for this tier.
    """
    ree_id = uuid4().hex
    handle = WorkbenchHandle(
        ree_id=ree_id,
        container_name=f"repo2ree-wb-{ree_id}",
        volume_name=f"repo2ree-ree-{ree_id}",
    )
    real_lookup = workbench_manager.lookup
    real_is_registered = workbench_manager.is_registered
    monkeypatch.setattr(
        workbench_manager,
        "lookup",
        lambda rid: handle if rid == ree_id else real_lookup(rid),
    )
    monkeypatch.setattr(
        workbench_manager,
        "is_registered",
        lambda rid: rid == ree_id or real_is_registered(rid),
    )
    return handle


@pytest.fixture
def staging_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-test upload staging dir, so tests can assert on staged files."""
    from repo2ree_api.settings import service_settings

    staging = tmp_path / "upload-staging"
    monkeypatch.setattr(service_settings, "UPLOAD_STAGING_DIR", staging)
    return staging
