"""The runtime command-plan endpoint: a stateless projection of a substrate.

Container-free — it delegates to the core projection and needs no workbench.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from repo2ree_api.runtime_plan import runtime_plan_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(runtime_plan_router)
    return TestClient(app)


def test_container_docker_entry_returns_three_phase_plan() -> None:
    client = _client()
    resp = client.post("/api/v1/runtime/command-plan", json={"kind": "container", "engine": "docker"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "container(docker)"
    assert [p["id"] for p in body["phases"]] == ["pre", "exec", "post"]
    assert any("docker load" in c["display"] for c in body["phases"][0]["commands"])


def test_container_podman_entry_uses_podman_binary() -> None:
    client = _client()
    resp = client.post("/api/v1/runtime/command-plan", json={"kind": "container", "engine": "podman"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "container(podman)"
    assert any("podman load" in c["display"] for c in body["phases"][0]["commands"])


def test_local_entry_includes_activate_verbatim() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/runtime/command-plan",
        json={"kind": "local", "activate": "source .venv/bin/activate"},
    )
    assert resp.status_code == 200
    exec_phase = next(p for p in resp.json()["phases"] if p["id"] == "exec")
    assert "source .venv/bin/activate" in exec_phase["commands"][0]["display"]


def test_custom_entry_shows_script_path() -> None:
    client = _client()
    resp = client.post(
        "/api/v1/runtime/command-plan",
        json={"kind": "custom", "enter_script": "scripts/my-env"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "custom"
    assert any("scripts/my-env" in c["display"] for phase in body["phases"] for c in phase["commands"])


def test_unknown_kind_is_rejected() -> None:
    client = _client()
    resp = client.post("/api/v1/runtime/command-plan", json={"kind": "nope"})
    assert resp.status_code == 422
