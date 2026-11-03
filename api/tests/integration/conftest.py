"""Fixtures for the real-component API integration tier.

The tier runs the API under uvicorn and a store's workbench as real processes
(see ``api_integration_bench``), and drives them over HTTP the way a client
does. Every REE it creates is created in the tier's store and deleted from it
afterwards.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from api_integration_bench import REQUEST_TIMEOUT, STORE_ID, TEST_RESULTS_DIR, ReeFilmstrip, Stack, running_stack

from repo2ree_testbed.artifacts import case_dir
from repo2ree_testbed.run_watch import NETWORK_RUN, client_getter, settle_run


@pytest.fixture(scope="session")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Stack]:
    """The API and the store's workbench, for the whole session: they hold no per-test state."""
    with running_stack(tmp_path_factory.mktemp("api-itest"), TEST_RESULTS_DIR) as running:
        yield running


@pytest.fixture(scope="session")
def client(stack: Stack) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=stack.base_url, timeout=REQUEST_TIMEOUT) as client:
        yield client


@pytest.fixture
def filmstrip(client: httpx.Client, request: pytest.FixtureRequest) -> ReeFilmstrip:
    """Per-test REE snapshot recorder, written beside the trace capture."""
    return ReeFilmstrip(client, case_dir(request.node.nodeid) / "state.ndjson")


@pytest.fixture
def ree(client: httpx.Client) -> Iterator[dict[str, Any]]:
    """A real REE, created in the tier's store; deleted from it afterwards.

    The delete is idempotent here: a test that already deleted its REE just gets a 404 back.
    """
    response = client.post("/api/v1/rees", json={"name": "api-itest", "store_id": STORE_ID})
    assert response.status_code == 200, response.text
    run = response.json()
    ree_id = run["ree_id"]
    try:
        assert wait_for_run(client, ree_id, run["run_id"]) == "succeeded"
        yield client.get(f"/api/v1/rees/{ree_id}").json()
    finally:
        client.delete(f"/api/v1/rees/{ree_id}")


def wait_for_run(client: httpx.Client, ree_id: str, run_id: str) -> str:
    """Wait for the background run to settle; return its status."""
    return str(settle_run(client_getter(client), ree_id, run_id, NETWORK_RUN).run["status"])
