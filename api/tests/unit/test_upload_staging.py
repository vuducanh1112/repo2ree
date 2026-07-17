"""Host-side upload staging: the init → PUT bytes leg of the upload flow.

Staging is the only host persistence in the REE flow, and everything up to
``docker cp`` is host-only — so this whole leg is real here: real routes,
real token allocation, real bytes on the real (per-test) staging dir.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.storage.upload_staging import (
    InvalidUploadTokenError,
    UnknownUploadTokenError,
    UploadTooLargeError,
    discard_expired_uploads,
    discard_staged_upload,
    new_upload_token,
    stage_upload_stream,
    staged_upload_path,
)
from repo2ree_supervisor import WorkbenchHandle


def _mint(staging_dir: Path, token: str) -> Path:
    """Stand in for upload-init: the empty marker that entitles a PUT."""
    staging_dir.mkdir(parents=True, exist_ok=True)
    path = staged_upload_path(token)
    path.touch()
    return path


# ================================================
# Routes
# ================================================


def test_upload_init_allocates_token_and_url(
    client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path
) -> None:
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/source:upload-init",
        json={"file_name": "project.zip", "size": 3, "content_type": "application/zip"},
    )
    assert resp.status_code == 200, resp.text
    upload = resp.json()
    token = upload["upload_token"]
    assert upload["upload_url"] == f"/api/v1/rees/{online_ree.ree_id}/source:upload/{token}"

    expires_at = datetime.fromisoformat(upload["expires_at"].replace("Z", "+00:00"))
    assert expires_at > datetime.now(UTC) + timedelta(minutes=50)

    # init mints an empty marker (proof the token was issued); bytes land on PUT
    assert staged_upload_path(token).exists()
    assert staged_upload_path(token).stat().st_size == 0


def test_upload_init_for_unknown_ree_is_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/rees/nope/source:upload-init",
        json={"file_name": "project.zip", "size": 3, "content_type": "application/zip"},
    )
    assert resp.status_code == 404


def test_put_bytes_lands_in_staging(client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path) -> None:
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/source:upload-init",
        json={"file_name": "project.zip", "size": 18, "content_type": "application/zip"},
    )
    token = resp.json()["upload_token"]

    data = b"zip-bytes-stand-in"
    resp = client.put(f"/api/v1/rees/{online_ree.ree_id}/source:upload/{token}", content=data)
    assert resp.status_code == 200
    body = resp.json()
    assert body["upload_token"] == token
    assert body["stored_at"]
    assert staged_upload_path(token).read_bytes() == data


def test_put_rejects_declared_size_mismatch(client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path) -> None:
    init = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/source:upload-init",
        json={"file_name": "project.zip", "size": 10, "content_type": "application/zip"},
    )
    token = init.json()["upload_token"]

    resp = client.put(f"/api/v1/rees/{online_ree.ree_id}/source:upload/{token}", content=b"short")

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "upload_size_mismatch"
    assert staged_upload_path(token).read_bytes() == b""


def test_upload_init_rejects_declared_size_over_limit(
    client: TestClient,
    online_ree: WorkbenchHandle,
    staging_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from repo2ree_api.settings import service_settings

    monkeypatch.setattr(service_settings, "UPLOAD_MAX_BYTES", 8)
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/source:upload-init",
        json={"file_name": "project.zip", "size": 9, "content_type": "application/zip"},
    )

    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "upload_too_large"


def test_put_bytes_for_unknown_ree_is_404(client: TestClient, staging_dir: Path) -> None:
    resp = client.put("/api/v1/rees/nope/source:upload/tok-1", content=b"data")
    assert resp.status_code == 404
    assert not staged_upload_path("tok-1").exists()


def test_put_bytes_with_unminted_token_is_404(
    client: TestClient, online_ree: WorkbenchHandle, staging_dir: Path
) -> None:
    # A request cannot invent its own token: only upload-init mints one, so an
    # attacker cannot land arbitrary files on the host outside the init flow.
    resp = client.put(f"/api/v1/rees/{online_ree.ree_id}/source:upload/tok-invented", content=b"data")
    assert resp.status_code == 404
    assert not staged_upload_path("tok-invented").exists()


# ================================================
# Helpers
# ================================================


def test_tokens_are_unique(staging_dir: Path) -> None:
    tokens = {new_upload_token()["upload_token"] for _ in range(50)}
    assert len(tokens) == 50


def test_stage_upload_stream_writes_chunks_in_order(staging_dir: Path) -> None:
    _mint(staging_dir, "tok-stream")

    async def chunks():
        yield b"zip-"
        yield b""
        yield b"bytes"

    path = asyncio.run(stage_upload_stream("tok-stream", chunks()))

    assert path == staged_upload_path("tok-stream")
    assert path.read_bytes() == b"zip-bytes"


def test_stage_upload_stream_rejects_unminted_token(staging_dir: Path) -> None:
    async def chunks():
        yield b"data"

    with pytest.raises(UnknownUploadTokenError):
        asyncio.run(stage_upload_stream("tok-unminted", chunks()))

    assert not staged_upload_path("tok-unminted").exists()


def test_stage_upload_stream_resets_to_marker_on_failure(staging_dir: Path) -> None:
    _mint(staging_dir, "tok-fail")

    async def chunks():
        yield b"partial"
        raise RuntimeError("client disconnected")

    with pytest.raises(RuntimeError, match="client disconnected"):
        asyncio.run(stage_upload_stream("tok-fail", chunks()))

    # The partial bytes must not survive, but the token stays minted (empty
    # marker) so the client can retry the PUT until the TTL.
    assert staged_upload_path("tok-fail").read_bytes() == b""


def test_discard_is_idempotent(staging_dir: Path) -> None:
    staging_dir.mkdir(parents=True)
    staged_upload_path("tok-2").write_bytes(b"data")
    discard_staged_upload("tok-2")
    assert not staged_upload_path("tok-2").exists()
    discard_staged_upload("tok-2")  # second discard must not raise


# ================================================
# Guardrails
# ================================================


@pytest.mark.parametrize("token", ["../escape", "a/b", "", "x" * 129, "tok\x00"])
def test_traversal_and_malformed_tokens_are_rejected(token: str) -> None:
    # A request-supplied token must never resolve outside the staging dir.
    with pytest.raises(InvalidUploadTokenError):
        staged_upload_path(token)


def test_upload_complete_with_traversal_token_is_400(client: TestClient, online_ree: WorkbenchHandle) -> None:
    # The PUT route's token rides the URL path, where routing already blocks
    # slashes — but upload-complete takes the token from the JSON body, so it
    # must be validated before it touches a path.
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/source:upload-complete",
        json={"upload_token": "../escape", "archive_name": "project.zip"},
    )
    assert resp.status_code == 400


def test_stage_upload_stream_rejects_oversized_body(staging_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from repo2ree_api.settings import service_settings

    monkeypatch.setattr(service_settings, "UPLOAD_MAX_BYTES", 8)
    _mint(staging_dir, "tok-big")

    async def chunks():
        yield b"12345"
        yield b"67890"

    with pytest.raises(UploadTooLargeError):
        asyncio.run(stage_upload_stream("tok-big", chunks()))
    # The partial bytes must not survive the rejection, but the minted token
    # remains retryable until its TTL.
    assert staged_upload_path("tok-big").read_bytes() == b""


def test_expired_staged_uploads_are_swept(staging_dir: Path) -> None:
    import os

    staging_dir.mkdir(parents=True)
    stale = staged_upload_path("tok-stale")
    fresh = staged_upload_path("tok-fresh")
    stale.write_bytes(b"old")
    fresh.write_bytes(b"new")
    two_hours_ago = datetime.now(UTC).timestamp() - 7200
    os.utime(stale, (two_hours_ago, two_hours_ago))

    discard_expired_uploads()

    assert not stale.exists()
    assert fresh.exists()
