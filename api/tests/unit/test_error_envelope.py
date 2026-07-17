"""The API's error contract: every failure is shaped into the error envelope.

The Docker-gated integration tier proves the envelope for one shape (string
detail) on a live stack; this tier pins the full contract unconditionally —
each exception-handler branch directly, and the container-free routes that
raise through them over real HTTP.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from repo2ree_api.deps import workbench_manager
from repo2ree_api.main import (
    http_exception_handler,
    unhandled_exception_handler,
    workbench_unavailable_handler,
)
from repo2ree_supervisor import WorkbenchHandle, WorkbenchUnavailableError

# ================================================
# Helpers
# ================================================


def _body(response: JSONResponse) -> dict[str, Any]:
    return json.loads(bytes(response.body))


def _request() -> Request:
    # The handlers ignore the request; a minimal ASGI scope satisfies the signature.
    return Request(scope={"type": "http", "method": "GET", "path": "/", "headers": []})


# ================================================
# Handler shapes (each branch, called directly)
# ================================================


def test_string_detail_becomes_envelope():
    exc = HTTPException(status_code=404, detail="REE x not found")
    response = asyncio.run(http_exception_handler(_request(), exc))
    assert response.status_code == 404
    assert _body(response) == {
        "error": {"code": "http_404", "message": "REE x not found", "details": None, "retryable": False}
    }


def test_dict_detail_maps_code_message_details():
    exc = HTTPException(
        status_code=409,
        detail={"code": "version_conflict", "message": "stale version", "details": {"expected": "v2"}},
    )
    response = asyncio.run(http_exception_handler(_request(), exc))
    assert response.status_code == 409
    assert _body(response) == {
        "error": {
            "code": "version_conflict",
            "message": "stale version",
            "details": {"expected": "v2"},
            "retryable": False,
        }
    }


def test_dict_detail_without_code_falls_back_to_status_code():
    exc = HTTPException(status_code=400, detail={"message": "bad input"})
    response = asyncio.run(http_exception_handler(_request(), exc))
    assert _body(response)["error"]["code"] == "http_400"
    assert _body(response)["error"]["message"] == "bad input"


def test_pre_shaped_envelope_passes_through_unchanged():
    detail = {"error": {"code": "custom", "message": "already shaped", "details": {"k": 1}}}
    exc = HTTPException(status_code=422, detail=detail)
    response = asyncio.run(http_exception_handler(_request(), exc))
    assert response.status_code == 422
    assert _body(response) == {
        "error": {
            "code": "custom",
            "message": "already shaped",
            "details": {"k": 1},
            "retryable": False,
        }
    }


def test_workbench_unavailable_maps_to_503():
    response = asyncio.run(workbench_unavailable_handler(_request(), WorkbenchUnavailableError("gone")))
    assert response.status_code == 503
    assert _body(response)["error"]["code"] == "workbench_unavailable"
    assert _body(response)["error"]["retryable"] is True


def test_unhandled_exception_maps_to_500_internal_error():
    response = asyncio.run(unhandled_exception_handler(_request(), RuntimeError("boom")))
    assert response.status_code == 500
    body = _body(response)
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "An internal error occurred"
    assert body["error"]["retryable"] is False


# ================================================
# Wiring over real HTTP (container-free routes)
# ================================================


def test_unknown_ree_yields_404_envelope(client: TestClient):
    """Real path: empty registry, no patching — lookup finds no entry."""
    resp = client.get("/api/v1/rees/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "http_404"
    assert "not found" in body["error"]["message"]


def test_request_validation_uses_error_envelope(client: TestClient):
    resp = client.post("/api/v1/rees", json={"origin_url": "https://example.org/repo.git"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "request_validation_failed"
    assert body["error"]["message"] == "Request validation failed"
    assert body["error"]["details"]["violations"]


def test_registered_but_unreachable_ree_yields_503(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """A REE in the registry whose container is down: 503, not 404.

    Staged at the seam: ``is_registered`` says yes, the real ``lookup`` (empty
    registry) returns no live handle — the state a crashed workbench leaves.
    """
    monkeypatch.setattr(workbench_manager, "is_registered", lambda rid: rid == "down-ree")
    resp = client.get("/api/v1/rees/down-ree")
    assert resp.status_code == 503
    assert resp.json()["error"]["message"] == "Workbench unavailable for this REE"


def test_transport_failure_mid_request_yields_503_envelope(
    client: TestClient, online_ree: WorkbenchHandle, monkeypatch: pytest.MonkeyPatch
):
    """A container dying mid-query surfaces as the workbench_unavailable envelope.

    The seam failing *is* the scenario: ``get_workspace`` raises the same
    ``WorkbenchUnavailableError`` the real transport raises when docker exec
    reports the container gone.
    """

    def _gone(handle: Any) -> dict[str, Any]:
        raise WorkbenchUnavailableError("docker exec exited 137 — container gone or stopping")

    monkeypatch.setattr(workbench_manager, "get_workspace", _gone)
    resp = client.get(f"/api/v1/rees/{online_ree.ree_id}")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "workbench_unavailable"
