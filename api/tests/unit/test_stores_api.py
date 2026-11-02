"""REEs served by stores: the stores, their workbenches' admission, and REEs while a store is offline."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from repo2ree_api import store_admin
from repo2ree_api.deps import ree_registry, store_registry, workbench_connections
from repo2ree_api.settings import service_settings
from repo2ree_protocol.workbench import WorkbenchHello


@pytest.fixture
def lab() -> str:
    store_id = f"lab-{len(store_registry.all())}"
    store_registry.add(store_id, "A lab")
    return store_id


def _served(store_id: str) -> str | None:
    """The workbench serving ``store_id`` once its hello is handled (admission runs after it arrives)."""
    deadline = time.monotonic() + 5
    while (served := workbench_connections.store_workbench(store_id)) is None and time.monotonic() < deadline:
        time.sleep(0.01)
    return served


def _hello(store_id: str, token: str, workbench_id: str = "wb-store") -> str:
    return WorkbenchHello(
        workbench_id=workbench_id, mode="external", store_id=store_id, enrollment_token=token
    ).model_dump_json()


def test_a_store_workbench_is_admitted_with_its_store_token_and_listed(client: TestClient, lab: str) -> None:
    token = store_registry.mint_token(lab)

    with client.websocket_connect("/workbench/connect") as socket:
        socket.send_text(_hello(lab, token))
        assert _served(lab) == "wb-store"
        listed = {store["store_id"]: store for store in client.get("/api/v1/stores").json()["stores"]}
        assert listed[lab]["connected"] is True
        assert listed[lab]["workbench_id"] == "wb-store"

    listed = {store["store_id"]: store for store in client.get("/api/v1/stores").json()["stores"]}
    assert listed[lab]["connected"] is False


@pytest.mark.parametrize("token", ["", "not-a-token"])
def test_a_store_workbench_without_its_token_is_refused(client: TestClient, lab: str, token: str) -> None:
    other = f"{lab}-other"
    store_registry.add(other)
    minted_for_other = store_registry.mint_token(other)

    for presented in (token, minted_for_other):
        with client.websocket_connect("/workbench/connect") as socket:
            socket.send_text(_hello(lab, presented))
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_text()
        assert closed.value.code == 1008


def test_a_second_workbench_for_a_served_store_is_refused(client: TestClient, lab: str) -> None:
    token = store_registry.mint_token(lab)

    with client.websocket_connect("/workbench/connect") as first:
        first.send_text(_hello(lab, token, "wb-first"))
        assert _served(lab) == "wb-first"
        with client.websocket_connect("/workbench/connect") as second:
            second.send_text(_hello(lab, token, "wb-second"))
            with pytest.raises(WebSocketDisconnect) as closed:
                second.receive_text()
        assert closed.value.code == 1008
        assert workbench_connections.store_workbench(lab) == "wb-first"


def test_an_ree_in_an_offline_store_is_listed_but_answers_store_unavailable(client: TestClient, lab: str) -> None:
    ree_registry.create("ree-offline", "Offline study", lab)
    try:
        listed = {item["ree_id"]: item for item in client.get("/api/v1/rees").json()["items"]}
        assert listed["ree-offline"]["name"] == "Offline study"
        assert listed["ree-offline"]["location_id"] == lab

        response = client.get("/api/v1/rees/ree-offline")
        assert response.status_code == 503
        error = response.json()["error"]
        assert (error["code"], error["retryable"], error["details"]) == ("store_unavailable", True, {"store_id": lab})
    finally:
        ree_registry.delete("ree-offline")


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "x"},
        {"name": "x", "store_id": "lab-a", "location_id": "loc-1"},
        {"name": "x", "store_id": "lab-a", "image": "python:3.12"},
    ],
)
def test_an_ree_is_created_in_exactly_one_place(client: TestClient, payload: dict[str, str]) -> None:
    assert client.post("/api/v1/rees", json=payload).status_code == 422


def test_an_ree_is_not_created_in_a_store_that_is_not_registered(client: TestClient) -> None:
    response = client.post("/api/v1/rees", json={"name": "x", "store_id": "lab-nowhere"})
    assert response.status_code == 404


def test_the_operator_registers_a_store_and_mints_and_revokes_its_tokens(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(service_settings, "CONTROL_STATE_DIR", tmp_path)

    assert store_admin.main(["add", "lab-cli", "--label", "CLI lab"]) == 0
    assert store_admin.main(["token", "lab-cli"]) == 0
    token = capsys.readouterr().out.strip().splitlines()[-1]
    assert store_admin.main(["list"]) == 0
    assert "lab-cli\tCLI lab" in capsys.readouterr().out
    assert store_admin.main(["revoke", token[:8]]) == 0
    assert store_admin.main(["revoke", token[:8]]) == 1
    assert store_admin.main(["token", "lab-missing"]) == 2
