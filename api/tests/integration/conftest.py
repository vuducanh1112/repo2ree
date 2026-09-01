"""Fixtures for the real-component API integration tier.

These tests run the actual FastAPI app over HTTP (via ``TestClient``) against
the real module-level ``WorkbenchManager`` — real ``docker run`` /
``docker exec`` transport, real workbench containers, real ``/ree`` volumes.
Nothing is mocked; like the supervisor e2e, the suite skips (never fakes)
when Docker or the workbench image is absent.

Host-side state (upload staging, the workbench registry) is redirected into a
throwaway directory via env vars *before* the app module —
and with it the workbench-manager singleton — is imported, so a developer's
``.env`` or live registry can't leak into the tests.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

import pytest

# The tier's constants and its recorder live in a module of their own, not
# here: the test modules import them by name, and a bare ``conftest`` import
# resolves to whichever suite's conftest pytest loaded last. See that module's
# docstring.
from api_integration_bench import (
    EXEC_BUNDLE,
    SNAPSHOT_DIR,
    TEST_RESULTS_DIR,
    TOOLS_BUNDLE,
    WORKBENCH_IMAGE,
    ReeFilmstrip,
)
from websockets.asyncio.server import ServerConnection, serve

# Must be set before the in-test agent constructs its DockerRuntime.
os.environ.setdefault("REPO2REE_EXEC_BUNDLE", str(EXEC_BUNDLE))
os.environ.setdefault("REPO2REE_TOOLS_BUNDLE", str(TOOLS_BUNDLE))

# Env vars take precedence over .env in pydantic-settings, and the settings
# (plus the registry singleton built from them) are read at import time — so
# this must run before any repo2ree_api import below.
_state_dir = Path(tempfile.mkdtemp(prefix="repo2ree-api-itest-"))
os.environ["UPLOAD_STAGING_DIR"] = str(_state_dir / "upload-staging")
os.environ["WORKBENCH_REGISTRY_FILE"] = str(_state_dir / "workbench-registry.json")
os.environ["REE_INDEX_FILE"] = str(_state_dir / "ree-index.json")
os.environ["RUN_REGISTRY_DIR"] = str(_state_dir / "runs")
# OpenTelemetry's set_tracer_provider is honored once per process, so two API
# tiers in one pytest run share a single provider baked to whichever tier booted
# first — the other's spans silently flow to the wrong file. Just runs the tiers
# as separate processes; this turns the unsafe `pytest api/tests` path into a
# loud, explained failure instead of wrong traces.
_claimed = os.environ.get("_REPO2REE_TRACE_TIER")
if _claimed and _claimed != "api-integration":
    raise RuntimeError(
        f"Both {_claimed} and api-integration tiers loaded in one pytest process; their spans "
        "collide on OpenTelemetry's set-once global provider. Run them separately: "
        "`just api-unit-tests` / `just api-integration-tests`, or `pytest api/tests/unit` "
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

from repo2ree_agent.control.connection import run_agent  # noqa: E402
from repo2ree_agent.runtimes.docker import DockerRuntime  # noqa: E402
from repo2ree_agent.service import WorkbenchService  # noqa: E402
from repo2ree_api.deps import agent_registry  # noqa: E402
from repo2ree_api.main import app  # noqa: E402
from repo2ree_protocol.agent import ws_hello_adapter  # noqa: E402
from repo2ree_supervisor import AgentConnection, WorkbenchUnavailableError  # noqa: E402

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
    with TestClient(app) as client, _connected_agent():
        yield client


@pytest.fixture
def filmstrip(client: TestClient, request: pytest.FixtureRequest) -> ReeFilmstrip:
    """Per-test REE snapshot recorder, written beside the trace capture."""
    return ReeFilmstrip(client, SNAPSHOT_DIR / f"{request.node.name}.ndjson")


@pytest.fixture
def ree(client: TestClient, request: pytest.FixtureRequest) -> Iterator[dict[str, Any]]:
    """A real REE backed by a freshly provisioned workbench container.

    Teardown snapshots the container's logs into ``test-results/`` for
    post-run inspection, then deletes the REE (container + volumes) through
    the API. The delete is idempotent here: a test that already deleted its
    REE just gets a 404 back.
    """
    # Drive the image this tier gates on, passed per-request like a real client.
    resp = client.post(
        "/api/v1/rees",
        json={"name": "api-itest", "workbench_image": WORKBENCH_IMAGE},
    )
    assert resp.status_code == 200, resp.text
    run = resp.json()
    ree_id = run["ree_id"]
    try:
        # Provisioning is a background run now (so the image pull streams live);
        # wait for it before yielding the fully-provisioned workspace.
        assert _wait_for_provision(client, ree_id, run["run_id"]) == "succeeded"
        workspace = client.get(f"/api/v1/rees/{ree_id}").json()
        yield workspace
    finally:
        _dump_workbench_logs(ree_id, request.node.name)
        client.delete(f"/api/v1/rees/{ree_id}")


def _wait_for_provision(client: TestClient, ree_id: str, run_id: str, timeout_seconds: int = 180) -> str:
    """Poll the provisioning run until it reaches a terminal status."""
    terminal = frozenset({"succeeded", "failed", "canceled"})
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()["status"]
        if status in terminal:
            return str(status)
        time.sleep(1.0)
    raise AssertionError(f"provisioning run {run_id} did not finish within {timeout_seconds}s")


# ================================================
# Helpers
# ================================================


@contextmanager
def _connected_agent() -> Iterator[None]:
    """Run the real outbound agent against the app's module-level registry.

    TestClient does not expose a TCP WebSocket endpoint, so this fixture mirrors
    the production /agent/connect bridge with a tiny in-test socket server: the
    real agent dials out, the server registers an AgentConnection into the same
    registry the API's WorkbenchManager uses, and HTTP requests exercise the
    normal manager/client path.
    """
    port = _free_port()
    loop = asyncio.new_event_loop()
    task_holder: list[asyncio.Task[None]] = []

    async def handler(ws: ServerConnection) -> None:
        def send_text(text: str) -> None:
            asyncio.run_coroutine_threadsafe(ws.send(text), loop)

        raw_hello = await ws.recv()
        hello = ws_hello_adapter.validate_json(raw_hello if isinstance(raw_hello, str) else raw_hello.decode())
        connection = AgentConnection(send_text=send_text, hello=hello)
        agent_registry.register(hello.agent_id, connection)
        try:
            async for message in ws:
                connection.on_message(message if isinstance(message, str) else message.decode())
        finally:
            connection.close()
            agent_registry.unregister(hello.agent_id, connection)

    async def serve_and_dial() -> None:
        async with serve(handler, "127.0.0.1", port):
            runtime = DockerRuntime("dind")
            await run_agent(
                f"ws://127.0.0.1:{port}/agent/connect",
                WorkbenchService({runtime.runtime_name: runtime}),
                "api-itest-agent",
                docker_mode="dind",
            )

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        task = loop.create_task(serve_and_dial())
        task_holder.append(task)
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)
        loop.close()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    _wait_until_agent_connected("api-itest-agent")
    try:
        yield
    finally:
        if task_holder:
            loop.call_soon_threadsafe(task_holder[0].cancel)
        thread.join(timeout=10)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_agent_connected(agent_id: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            agent_registry.pick(agent_id)
            return
        except WorkbenchUnavailableError:
            time.sleep(0.05)
    raise RuntimeError(f"agent {agent_id!r} did not dial in within {timeout}s")


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
