"""Real-component integration tests: the API over HTTP against live workbenches.

This tier sits between the core flow test (real handlers, no Docker) and the
supervisor e2e (real transport, no HTTP): it exercises the HTTP envelope —
routing, payload validation, the error-shape exception handlers, background
runs and their log feed — on top of the same real container transport the
supervisor e2e proves. Nothing is mocked; the module skips (never fakes)
when Docker or the workbench image is absent.

Flow exercised over real HTTP + ``docker exec``:
    create (provision) -> upload-init -> upload bytes -> upload-complete
        -> poll the background run + read its log feed
        -> write/read a file -> seal -> download the sealed archive -> delete
"""

from __future__ import annotations

import shutil
import subprocess
import time
import zipfile
from io import BytesIO
from typing import Any

import pytest

# The tier's skip gate lives in conftest alongside the `ree` fixture so the
# two stay in lockstep.
from conftest import bundles_present
from fastapi.testclient import TestClient

# ================================================
# Constants
# ================================================


RUN_TIMEOUT_SECONDS = 180
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})


# ================================================
# Skip gate
# ================================================


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "version"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available() or not bundles_present(),
    reason="api integration tier needs docker + the executor/tools bundles (run: make e2e-bundles)",
)


# ================================================
# Helpers
# ================================================


def _project_zip() -> bytes:
    """A small in-memory source archive to stand in for an uploaded project."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.md", "# demo project\n")
        zf.writestr("requirements.txt", "requests==2.31.0\n")
        zf.writestr("app.py", "print('hello')\n")
    return buf.getvalue()


def _wait_for_run(client: TestClient, ree_id: str, run_id: str) -> str:
    """Poll the run endpoint until the background run reaches a terminal status."""
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        status = resp.json()["status"]
        if status in TERMINAL_RUN_STATUSES:
            return status
        time.sleep(1.0)
    pytest.fail(f"run {run_id} did not reach a terminal status within {RUN_TIMEOUT_SECONDS}s")


def _upload_source(client: TestClient, ree_id: str, data: bytes, archive_name: str) -> dict[str, Any]:
    """Drive the three-step upload flow; return the background run summary."""
    resp = client.post(
        f"/api/v1/rees/{ree_id}/source:upload-init",
        json={"file_name": archive_name, "size": len(data), "content_type": "application/zip"},
    )
    assert resp.status_code == 200, resp.text
    upload = resp.json()

    resp = client.put(upload["upload_url"], content=data)
    assert resp.status_code == 200, resp.text

    resp = client.post(
        f"/api/v1/rees/{ree_id}/source:upload-complete",
        json={"upload_token": upload["upload_token"], "archive_name": archive_name},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ================================================
# Flow
# ================================================


def test_api_ree_lifecycle(client: TestClient, ree: dict[str, Any]) -> None:
    ree_id = ree["ree_id"]
    assert ree["status"] == "draft"

    # the freshly provisioned REE is visible in the listing
    resp = client.get("/api/v1/rees")
    assert resp.status_code == 200
    assert any(item.get("ree_id") == ree_id for item in resp.json()["items"])

    # --- source upload: staging -> docker cp -> extract pipeline --------
    run = _upload_source(client, ree_id, _project_zip(), "project.zip")
    assert run["operation"] == "source"
    assert _wait_for_run(client, ree_id, run["run_id"]) == "succeeded"

    # the run's log feed carried the real pipeline steps back over HTTP
    resp = client.get(f"/api/v1/rees/{ree_id}/runs/{run['run_id']}/logs")
    assert resp.status_code == 200
    logs = resp.json()
    assert logs["run_status"] == "succeeded"
    assert logs["entries"]

    # the extracted source landed in the workspace on the workbench volume
    resp = client.get(f"/api/v1/rees/{ree_id}")
    assert resp.status_code == 200
    workspace = resp.json()
    assert any(f.get("path") == "README.md" for f in workspace["files"])

    # --- write a file over HTTP, read the raw bytes back ----------------
    resp = client.put(
        f"/api/v1/rees/{ree_id}/files/content",
        json={"path": "build.sh", "content": "echo build\n"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(f"/api/v1/rees/{ree_id}/files/raw", params={"path": "build.sh"})
    assert resp.status_code == 200
    assert resp.content == b"echo build\n"

    # --- seal, then download the sealed archive -------------------------
    resp = client.post(f"/api/v1/rees/{ree_id}/ree:seal", json={})
    assert resp.status_code == 200, resp.text
    sealed = resp.json()
    assert sealed["ree_session"]["seal_hash"].startswith("sha256:")

    resp = client.get(f"/api/v1/rees/{ree_id}/ree-archive")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        assert zf.namelist()


def test_delete_tears_down_workbench(client: TestClient, ree: dict[str, Any]) -> None:
    ree_id = ree["ree_id"]

    resp = client.delete(f"/api/v1/rees/{ree_id}")
    assert resp.status_code == 200
    assert resp.json()["state"] == "deleted"

    # the REE is gone from the API's view, with the canonical error envelope
    resp = client.get(f"/api/v1/rees/{ree_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "http_404"


# ================================================
# Error envelope
# ================================================


def test_unknown_ree_yields_error_envelope(client: TestClient) -> None:
    """The exception handler shapes HTTPException into the error envelope."""
    resp = client.get("/api/v1/rees/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "http_404"
    assert "not found" in body["error"]["message"]
    assert body["error"]["details"] is None


def test_archive_before_seal_returns_a_draft_bundle(client: TestClient, ree: dict[str, Any]) -> None:
    """An unsealed REE downloads as a draft bundle on demand, not an error.

    Assembling the draft is the handoff path (loadable into another REE); only
    the sealed archive is the citable, seal-hashed artifact. See the
    ``ree-archive`` route.
    """
    resp = client.get(f"/api/v1/rees/{ree['ree_id']}/ree-archive")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert resp.content
