"""Stores, the tokens that admit their workbenches, and the REEs they serve."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from repo2ree_protocol.workbench import WorkbenchHello
from repo2ree_supervisor import (
    ReeRegistry,
    ReeRoute,
    ReeRouter,
    StoreClaimedError,
    StoreRegistry,
    StoreUnavailableError,
    UnknownStoreError,
    WorkbenchConnection,
    WorkbenchConnectionRegistry,
)


def _connection(workbench_id: str, store_id: str, nonce: str = "n1") -> WorkbenchConnection:
    hello = WorkbenchHello(workbench_id=workbench_id, store_id=store_id, nonce=nonce)
    return WorkbenchConnection(send_text=lambda text: None, hello=hello)


def test_a_token_admits_a_workbench_to_its_own_store_until_it_is_revoked(tmp_path: Path) -> None:
    stores = StoreRegistry(tmp_path / "stores.json")
    stores.add("lab-a", "Lab A")
    stores.add("lab-b")
    token = stores.mint_token("lab-a")

    assert stores.authenticate(token, "lab-a")
    assert not stores.authenticate(token, "lab-b")
    assert not stores.authenticate("", "lab-a")
    assert stores.revoke(token[:8]) == 1
    assert not stores.authenticate(token, "lab-a")


def test_only_digests_are_kept_and_only_by_their_owner(tmp_path: Path) -> None:
    path = tmp_path / "stores.json"
    stores = StoreRegistry(path)
    stores.add("lab-a")
    token = stores.mint_token("lab-a")

    assert token not in path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # Another process reads what this one wrote.
    assert StoreRegistry(path).authenticate(token, "lab-a")


def test_a_store_is_registered_once_under_a_plain_id(tmp_path: Path) -> None:
    stores = StoreRegistry(tmp_path / "stores.json")
    stores.add("lab-a")

    with pytest.raises(ValueError, match="already registered"):
        stores.add("lab-a")
    for refused in ("", "../x", "a b", "-x"):
        with pytest.raises(ValueError, match="not a store id"):
            stores.add(refused)
    with pytest.raises(UnknownStoreError):
        stores.mint_token("lab-z")
    assert [record.store_id for record in stores.all()] == ["lab-a"]


def test_an_ree_keeps_what_was_last_seen_of_it(tmp_path: Path) -> None:
    rees = ReeRegistry(tmp_path / "rees.json")
    rees.create("ree-1", "First", "lab-a")
    rees.update_summary("ree-1", name="Renamed", status="sealed")
    rees.update_summary("ree-gone", name="x", status="draft")

    record = ReeRegistry(tmp_path / "rees.json").get("ree-1")
    assert record is not None
    assert (record.name, record.status, record.store_id) == ("Renamed", "sealed", "lab-a")
    with pytest.raises(ValueError, match="already registered"):
        rees.create("ree-1", "Again", "lab-a")
    rees.delete("ree-1")
    assert rees.all() == []


def test_a_store_is_served_by_one_workbench_at_a_time() -> None:
    connections = WorkbenchConnectionRegistry()
    first = _connection("wb-1", "lab-a")
    connections.register("wb-1", first)

    with pytest.raises(StoreClaimedError, match="wb-1"):
        connections.register("wb-2", _connection("wb-2", "lab-a"))
    # The same workbench reconnecting takes its place again.
    connections.register("wb-1", _connection("wb-1", "lab-a"))
    assert connections.store_workbench("lab-a") == "wb-1"
    assert connections.store_workbench("lab-b") is None


def test_an_ree_in_a_store_goes_to_whichever_workbench_serves_it(tmp_path: Path) -> None:
    rees = ReeRegistry(tmp_path / "rees.json")
    rees.create("ree-1", "First", "lab-a")
    connections = WorkbenchConnectionRegistry()
    router = ReeRouter(rees, connections)

    with pytest.raises(StoreUnavailableError, match="lab-a"):
        router.route("ree-1")

    connections.register("wb-1", _connection("wb-1", "lab-a"))
    assert router.route("ree-1") == ReeRoute(ree_id="ree-1", workbench_id="wb-1", store_id="lab-a")
    assert router.route("ree-unknown") is None
