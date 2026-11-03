"""The upload flow against uvicorn over TCP, timed against a stalled event loop.

uvicorn runs the API with its one production event loop, and the store's
workbench dials the real ``/workbench/connect`` route, so this catches the class
of bug where a blocking workbench call inside an async route starves the very
loop that must deliver its reply (a frozen API, workbench keepalive death).

The regression canary is timing: every request carries a hard client-side
deadline, so a loop-freeze fails the test quickly instead of hanging it.
"""

from __future__ import annotations

import os
import time
import zipfile
from io import BytesIO

import httpx
import pytest
from api_integration_bench import REQUEST_TIMEOUT, STORE_ID, Stack, tools_present

from repo2ree_testbed.run_watch import NETWORK_RUN, client_getter, settle_run

pytestmark = pytest.mark.skipif(
    not tools_present(), reason="the upload flow seals, which needs the tools bundle (run: just build-e2e-bundles)"
)


# Big enough that the sealed archive (and its ~4/3 base64 encoding) far exceeds
# uvicorn's 16 MiB WebSocket receive cap — the regression where one oversized
# frame killed the whole workbench connection and broke every download.
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
    """Wait for the background run to settle; return its status."""
    return str(settle_run(client_getter(client), ree_id, run_id, NETWORK_RUN).run["status"])


# ================================================
# Flow
# ================================================


def test_upload_over_real_server(stack: Stack) -> None:
    base_url = stack.base_url
    with httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT) as client:
        resp = client.post("/api/v1/rees", json={"name": "real-server-itest", "store_id": STORE_ID})
        assert resp.status_code == 200, resp.text
        run = resp.json()
        ree_id = run["ree_id"]
        try:
            assert _wait_for_run(client, ree_id, run["run_id"]) == "succeeded"

            # --- three-step upload over real TCP ------------------------
            data = _project_zip()
            resp = client.post(
                f"/api/v1/rees/{ree_id}/source:upload-init",
                json={"file_name": "project.zip", "size": len(data), "content_type": "application/zip"},
            )
            assert resp.status_code == 200, resp.text
            upload = resp.json()

            # The PUT is the async route that once blocked the event loop
            # against its own workbench reply. On the loop it must answer fast;
            # a regression trips REQUEST_TIMEOUT instead of hanging the suite.
            t0 = time.monotonic()
            resp = client.put(upload["upload_url"], content=data)
            put_elapsed = time.monotonic() - t0
            assert resp.status_code == 200, resp.text
            assert put_elapsed < 10.0, f"upload PUT took {put_elapsed:.1f}s — event loop likely stalled"

            # While the PUT ran, the loop stayed live: an unrelated endpoint
            # still answers within a tight bound.
            assert httpx.get(f"{base_url}/api/v1/workbenches", timeout=5.0).status_code == 200

            resp = client.post(
                f"/api/v1/rees/{ree_id}/source:upload-complete",
                json={"upload_token": upload["upload_token"], "archive_name": "project.zip"},
            )
            assert resp.status_code == 200, resp.text
            source_run = resp.json()
            assert _wait_for_run(client, ree_id, source_run["run_id"]) == "succeeded"

            # The run log narrates the copy: the step that used to fail silently.
            resp = client.get(f"/api/v1/rees/{ree_id}/runs/{source_run['run_id']}/logs")
            assert resp.status_code == 200
            messages = [entry["message"] for entry in resp.json()["entries"]]
            assert any("Copying staged archive" in m for m in messages)

            # The extracted source landed in the workspace.
            resp = client.get(f"/api/v1/rees/{ree_id}")
            assert resp.status_code == 200
            assert any(f.get("path") == "README.md" for f in resp.json()["workspace_files"])

            # --- seal (with source), download an archive over one WS frame --
            resp = client.post(f"/api/v1/rees/{ree_id}/ree:seal", json={"include_source": True})
            assert resp.status_code == 200, resp.text
            seal_run = resp.json()
            assert _wait_for_run(client, ree_id, seal_run["run_id"]) == "succeeded"

            resp = client.get(f"/api/v1/rees/{ree_id}/runs/{seal_run['run_id']}/logs")
            assert resp.status_code == 200
            messages = [entry["message"] for entry in resp.json()["entries"]]
            assert any("Preparing sealed artifacts" in message for message in messages)

            # The archive (> uvicorn's 16 MiB WS cap) must arrive intact via
            # chunked frames — one oversized frame used to kill the connection.
            resp = client.get(f"/api/v1/rees/{ree_id}/ree-archive", timeout=httpx.Timeout(240.0))
            assert resp.status_code == 200, resp.text
            assert len(resp.content) > LARGE_BLOB_BYTES
            with zipfile.ZipFile(BytesIO(resp.content)) as zf:
                assert zf.namelist()

            # The workbench connection survived the whole flow (no keepalive death,
            # no frame-cap kill).
            resp = client.get("/api/v1/workbenches")
            assert resp.status_code == 200
            assert resp.json()["workbenches"]
        finally:
            client.delete(f"/api/v1/rees/{ree_id}")
