"""Real-server integration test: the upload flow against uvicorn over TCP.

The TestClient tier next door (``test_api_workbench_flow``) drives the same
flow, but TestClient executes async routes on a different event loop than the
one pumping the agent's WebSocket — so it is structurally incapable of catching
the class of bug where a blocking agent call inside an async route starves the
very loop that must deliver its reply (a frozen API, agent keepalive death).
This tier closes that gap: uvicorn runs as a real subprocess with its one
production event loop, and the real agent dials the real ``/agent/connect``
route — which the fake in-test WS bridge in ``conftest`` bypasses.

The regression canary is timing: every request carries a hard client-side
deadline, so a loop-freeze fails the test quickly instead of hanging it.

Like the neighbouring tiers, this needs Docker and the workbench image and
skips (never fakes) when either is absent.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import httpx
import pytest

# The tier's workbench image lives in conftest so the skip gate and the
# provisioning request stay in lockstep.
from conftest import WORKBENCH_IMAGE, bundles_present

# ================================================
# Constants
# ================================================

TEST_RESULTS_DIR = Path(__file__).resolve().parents[3] / "test-artifacts" / "traces" / "api-real-server"

STARTUP_TIMEOUT_SECONDS = 30
RUN_TIMEOUT_SECONDS = 180
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})

# Hard per-request deadline. Every route this test touches answers in well
# under a second when healthy; a stalled event loop blows this bound fast.
REQUEST_TIMEOUT = httpx.Timeout(30.0)


# ================================================
# Skip gate
# ================================================


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "version"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available() or not bundles_present(),
    reason="real-server tier needs docker + the executor/tools bundles (run: make e2e-bundles)",
)


# ================================================
# Fixtures — uvicorn + agent as real subprocesses
# ================================================


@pytest.fixture
def server(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[str]:
    """Run uvicorn and the workbench agent as subprocesses; yield the base URL.

    Both use throwaway state under ``tmp_path`` so a developer's registry or
    staging dir can't leak in. Their stdout/stderr land in ``test-artifacts``
    so a failed run can still be inspected.
    """
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    out_dir = TEST_RESULTS_DIR / request.node.name
    out_dir.mkdir(parents=True, exist_ok=True)

    server_env = {
        **os.environ,
        "WORKBENCH_REGISTRY_FILE": str(tmp_path / "registry.json"),
        "UPLOAD_STAGING_DIR": str(tmp_path / "upload-staging"),
        "TRACE_FILE": str(out_dir / "traces.ndjson"),
    }
    agent_env = {
        **os.environ,
        "WORKBENCH_API_WS_URL": f"ws://127.0.0.1:{port}/agent/connect",
        "WORKBENCH_DOCKER_MODE": "dind",
        "WORKBENCH_AGENT_STATE_DIR": str(tmp_path / "agent-state"),
    }

    with (out_dir / "server.log").open("w") as server_log, (out_dir / "agent.log").open("w") as agent_log:
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "repo2ree_api.main:app", "--host", "127.0.0.1", "--port", str(port)],
            env=server_env,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )
        agent_proc = subprocess.Popen(
            [sys.executable, "-m", "repo2ree_agent"],
            env=agent_env,
            stdout=agent_log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_agent_connected(base_url)
            yield base_url
        finally:
            agent_proc.terminate()
            agent_proc.wait(timeout=10)
            server_proc.terminate()
            server_proc.wait(timeout=10)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_agent_connected(base_url: str) -> None:
    """Block until the server answers and lists a dialed-in agent."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/api/v1/agents", timeout=2.0)
            if resp.status_code == 200 and resp.json()["agents"]:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    pytest.fail(f"server + agent did not come up within {STARTUP_TIMEOUT_SECONDS}s")


# ================================================
# Helpers
# ================================================


# Big enough that the sealed archive (and its ~4/3 base64 encoding) far exceeds
# uvicorn's 16 MiB WebSocket receive cap — the regression where one oversized
# frame killed the whole agent connection and broke every download.
LARGE_BLOB_BYTES = 20 * 1024 * 1024


def _project_zip() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("README.md", "# real-server demo\n")
        zf.writestr("app.py", "print('hello')\n")
        # Incompressible payload, so the archive stays large end to end.
        zf.writestr("data/blob.bin", os.urandom(LARGE_BLOB_BYTES))
    return buf.getvalue()


def _wait_for_run(client: httpx.Client, ree_id: str, run_id: str) -> str:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()["status"]
        if status in TERMINAL_RUN_STATUSES:
            return status
        time.sleep(1.0)
    pytest.fail(f"run {run_id} did not reach a terminal status within {RUN_TIMEOUT_SECONDS}s")


# ================================================
# Flow
# ================================================


def test_upload_over_real_server(server: str) -> None:
    with httpx.Client(base_url=server, timeout=REQUEST_TIMEOUT) as client:
        # --- provision a workbench through the real stack ---------------
        # Drive the locally-built image this tier gates on, passed per-request
        # like a real client — never pull the published edge default.
        resp = client.post(
            "/api/v1/rees",
            json={"sourceMode": "upload", "name": "real-server-itest", "workbenchImage": WORKBENCH_IMAGE},
        )
        assert resp.status_code == 200, resp.text
        run = resp.json()
        ree_id = run["reeId"]
        try:
            assert _wait_for_run(client, ree_id, run["runId"]) == "succeeded"

            # --- three-step upload over real TCP ------------------------
            data = _project_zip()
            resp = client.post(
                f"/api/v1/rees/{ree_id}/source:upload-init",
                json={"fileName": "project.zip", "size": len(data), "contentType": "application/zip"},
            )
            assert resp.status_code == 200, resp.text
            upload = resp.json()

            # The PUT is the async route that once blocked the event loop
            # against its own agent reply. On the loop it must answer fast;
            # a regression trips REQUEST_TIMEOUT instead of hanging the suite.
            t0 = time.monotonic()
            resp = client.put(upload["uploadUrl"], content=data)
            put_elapsed = time.monotonic() - t0
            assert resp.status_code == 200, resp.text
            assert put_elapsed < 10.0, f"upload PUT took {put_elapsed:.1f}s — event loop likely stalled"

            # While the PUT ran, the loop stayed live: an unrelated endpoint
            # still answers within a tight bound.
            assert httpx.get(f"{server}/api/v1/agents", timeout=5.0).status_code == 200

            resp = client.post(
                f"/api/v1/rees/{ree_id}/source:upload-complete",
                json={"uploadToken": upload["uploadToken"], "archiveName": "project.zip"},
            )
            assert resp.status_code == 200, resp.text
            source_run = resp.json()
            assert _wait_for_run(client, ree_id, source_run["runId"]) == "succeeded"

            # The run log narrates the copy: the step that used to fail silently.
            resp = client.get(f"/api/v1/rees/{ree_id}/runs/{source_run['runId']}/logs")
            assert resp.status_code == 200
            messages = [entry["message"] for entry in resp.json()["entries"]]
            assert any("Copying staged archive" in m for m in messages)

            # The extracted source landed in the workspace.
            resp = client.get(f"/api/v1/rees/{ree_id}")
            assert resp.status_code == 200
            assert any(f.get("path") == "README.md" for f in resp.json()["files"])

            # --- seal (with source), download an archive over one WS frame --
            resp = client.post(f"/api/v1/rees/{ree_id}/ree:seal", json={"includeSource": True})
            assert resp.status_code == 200, resp.text

            # The archive (> uvicorn's 16 MiB WS cap) must arrive intact via
            # chunked frames — one oversized frame used to kill the connection.
            resp = client.get(f"/api/v1/rees/{ree_id}/ree-archive", timeout=httpx.Timeout(240.0))
            assert resp.status_code == 200, resp.text
            assert len(resp.content) > LARGE_BLOB_BYTES
            with zipfile.ZipFile(BytesIO(resp.content)) as zf:
                assert zf.namelist()

            # The agent connection survived the whole flow (no keepalive death,
            # no frame-cap kill).
            resp = client.get("/api/v1/agents")
            assert resp.status_code == 200
            assert resp.json()["agents"]
        finally:
            client.delete(f"/api/v1/rees/{ree_id}")
