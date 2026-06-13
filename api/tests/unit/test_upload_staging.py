"""Host-side upload staging: the init → PUT bytes leg of the upload flow.

Staging is the only host persistence in the REE flow, and everything up to
``docker cp`` is host-only — so this whole leg is real here: real routes,
real token allocation, real bytes on the real (per-test) staging dir.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from repo2ree_api.storage.upload_staging import (
    discard_staged_upload,
    new_upload_token,
    staged_upload_path,
)
from repo2ree_supervisor import WorkbenchHandle

# ================================================
# Routes
# ================================================


def test_upload_init_allocates_token_and_url(
    client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path
) -> None:
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/source:upload-init",
        json={"fileName": "project.zip", "size": 3, "contentType": "application/zip"},
    )
    assert resp.status_code == 200, resp.text
    upload = resp.json()
    token = upload["uploadToken"]
    assert upload["uploadUrl"] == f"/api/v1/rees/{online_ree.ree_id}/source:upload/{token}"

    expires_at = datetime.fromisoformat(upload["expiresAt"].replace("Z", "+00:00"))
    assert expires_at > datetime.now(UTC) + timedelta(minutes=50)

    # init allocates only the token; no bytes land until the PUT
    assert not staged_upload_path(token).exists()


def test_upload_init_for_unknown_ree_is_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/rees/nope/source:upload-init",
        json={"fileName": "project.zip", "size": 3, "contentType": "application/zip"},
    )
    assert resp.status_code == 404


def test_put_bytes_lands_in_staging(client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path) -> None:
    data = b"zip-bytes-stand-in"
    resp = client.put(f"/api/v1/rees/{online_ree.ree_id}/source:upload/tok-1", content=data)
    assert resp.status_code == 200
    body = resp.json()
    assert body["uploadToken"] == "tok-1"
    assert body["storedAt"]
    assert staged_upload_path("tok-1").read_bytes() == data


def test_put_bytes_for_unknown_ree_is_404(client: TestClient, staging_dir: Path) -> None:
    resp = client.put("/api/v1/rees/nope/source:upload/tok-1", content=b"data")
    assert resp.status_code == 404
    assert not staged_upload_path("tok-1").exists()


# ================================================
# Helpers
# ================================================


def test_tokens_are_unique() -> None:
    tokens = {new_upload_token()["uploadToken"] for _ in range(50)}
    assert len(tokens) == 50


def test_discard_is_idempotent(staging_dir: Path) -> None:
    staging_dir.mkdir(parents=True)
    staged_upload_path("tok-2").write_bytes(b"data")
    discard_staged_upload("tok-2")
    assert not staged_upload_path("tok-2").exists()
    discard_staged_upload("tok-2")  # second discard must not raise
