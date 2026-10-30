"""Archives a workbench uploads beside its control socket, and the download that serves one."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.authoring import seal
from repo2ree_api.deps import workbench_manager, workbench_transfers
from repo2ree_supervisor import ReceivedFile, WorkbenchHandle


def test_a_workbench_uploads_into_an_open_transfer_exactly_once(client: TestClient) -> None:
    path = workbench_transfers.open_upload()

    first = client.put(path, content=b"zip-bytes")
    again = client.put(path, content=b"zip-bytes")

    assert first.status_code == 204
    assert again.status_code == 404
    received = workbench_transfers.collect(path)
    try:
        assert received.path.read_bytes() == b"zip-bytes"
        assert received.sha256 == hashlib.sha256(b"zip-bytes").hexdigest()
    finally:
        received.path.unlink()


def test_a_guessed_transfer_token_is_refused(client: TestClient) -> None:
    assert client.put("/workbench/transfers/guessed", content=b"x").status_code == 404
    assert client.get("/workbench/transfers/guessed").status_code == 404


def test_a_workbench_fetches_an_offered_file_exactly_once(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "upload.tar.gz"
    source.write_bytes(b"source-archive")
    path = workbench_transfers.offer(source)
    try:
        first = client.get(path)
        again = client.get(path)
    finally:
        workbench_transfers.close(path)

    assert first.status_code == 200
    assert first.content == b"source-archive"
    assert again.status_code == 404


def test_the_transfer_route_is_not_part_of_the_public_api(client: TestClient) -> None:
    assert not any("/workbench/transfers" in route for route in client.get("/openapi.json").json()["paths"])


def test_the_archive_download_serves_the_uploaded_file_and_leaves_nothing_behind(
    client: TestClient, online_ree: WorkbenchHandle, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    archive = tmp_path / "archive.zip"
    archive.write_bytes(b"PK\x03\x04archive")

    def build(handle: Any) -> ReceivedFile:
        return ReceivedFile(archive, archive.stat().st_size, hashlib.sha256(archive.read_bytes()).hexdigest())

    monkeypatch.setattr(workbench_manager, "build_archive", build)
    # The download is named after the REE; this tier has no workbench to read the name from.
    monkeypatch.setattr(seal, "archive_download_filename", lambda handle: "hello.zip")
    response = client.get(f"/api/v1/rees/{online_ree.ree_id}/ree-archive")

    assert response.status_code == 200
    assert response.content == b"PK\x03\x04archive"
    assert response.headers["content-length"] == str(len(b"PK\x03\x04archive"))
    assert 'filename="hello.zip"' in response.headers["content-disposition"]
    assert not archive.exists()
