from __future__ import annotations

import zipfile
from io import BytesIO
from typing import Any

import pytest
from api_integration_bench import tools_present
from httpx import Client as TestClient

from repo2ree_testbed.run_watch import NETWORK_RUN, client_getter, settle_run

pytestmark = pytest.mark.skipif(
    not tools_present(), reason="api integration tier needs the tools bundle (run: just build-e2e-bundles)"
)


def _project_zip() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.md", "# demo project\n")
        zf.writestr("requirements.txt", "requests==2.31.0\n")
        zf.writestr("app.py", "print('hello')\n")
    return buf.getvalue()


def _wait_for_run(client: TestClient, ree_id: str, run_id: str) -> str:
    return str(settle_run(client_getter(client), ree_id, run_id, NETWORK_RUN).run["status"])


def _upload_source(client: TestClient, ree_id: str, data: bytes, archive_name: str) -> dict[str, Any]:
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
    payload: dict[str, Any] = resp.json()
    return payload


def test_api_ree_lifecycle(client: TestClient, ree: dict[str, Any]) -> None:
    ree_id = ree["ree_id"]
    assert ree["status"] == "draft"

    resp = client.get("/api/v1/rees")
    assert resp.status_code == 200
    assert any(item.get("ree_id") == ree_id for item in resp.json()["items"])

    run = _upload_source(client, ree_id, _project_zip(), "project.zip")
    assert run["operation"] == "acquire_source"
    assert _wait_for_run(client, ree_id, run["run_id"]) == "succeeded"

    resp = client.get(f"/api/v1/rees/{ree_id}/runs/{run['run_id']}/logs")
    assert resp.status_code == 200
    logs = resp.json()
    assert logs["run_status"] == "succeeded"
    assert logs["entries"]

    resp = client.get(f"/api/v1/rees/{ree_id}")
    assert resp.status_code == 200
    workspace = resp.json()
    assert any(f.get("path") == "README.md" for f in workspace["workspace_files"])

    resp = client.post(
        f"/api/v1/rees/{ree_id}/write-script",
        json={"path": "ree-scripts/build_experiment_environment.sh", "content": "echo build\n"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.get(
        f"/api/v1/rees/{ree_id}/files/raw", params={"path": "workspace/ree-scripts/build_experiment_environment.sh"}
    )
    assert resp.status_code == 200
    assert resp.content == b"echo build\n"

    resp = client.post(f"/api/v1/rees/{ree_id}/seal-ree", json={})
    assert resp.status_code == 200, resp.text
    seal_run = resp.json()
    assert seal_run["operation"] == "seal_ree"
    assert _wait_for_run(client, ree_id, seal_run["run_id"]) == "succeeded"
    sealed = client.get(f"/api/v1/rees/{ree_id}").json()
    assert sealed["ree"]["seal"]["ree_digest"].startswith("sha256:")

    resp = client.get(f"/api/v1/rees/{ree_id}/ree-archive")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        assert zf.namelist()


def test_delete_removes_the_ree_from_its_store(client: TestClient, ree: dict[str, Any]) -> None:
    ree_id = ree["ree_id"]

    resp = client.delete(f"/api/v1/rees/{ree_id}")
    assert resp.status_code == 200
    assert resp.json()["state"] == "deleted"

    resp = client.get(f"/api/v1/rees/{ree_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "http_404"


def test_unknown_ree_yields_error_envelope(client: TestClient) -> None:
    resp = client.get("/api/v1/rees/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "http_404"
    assert "not found" in body["error"]["message"]
    assert body["error"]["details"] is None


def test_archive_before_seal_returns_a_draft_bundle(client: TestClient, ree: dict[str, Any]) -> None:
    resp = client.get(f"/api/v1/rees/{ree['ree_id']}/ree-archive")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(resp.content)) as archive:
        assert "ree/.git/HEAD" in archive.namelist()
        assert "ree/ree.json" in archive.namelist()
        assert "ree.zip" not in archive.namelist()
