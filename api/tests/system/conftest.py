"""Fixtures for the system suite: a running deployment, reached only through its API.

The suite runs inside ``python -m repo2ree_testbed e2e`` (``just test-e2e-system``),
which owns the stack, passes its address, and collects the run's behaviour
recording afterwards. Every REE a test authors is downloaded before it is
released, as its owner would, so the recording holds each REE's Git history.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from system_client import Api

BASE_URL = os.environ.get("E2E_API_BASE_URL", "")
ARCHIVE_DIR = Path(os.environ.get("E2E_ARCHIVE_DIR", "test-artifacts/python/system/archives"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if BASE_URL:
        return
    skip = pytest.mark.skip(reason="the system suite drives a running stack: run it with just test-e2e-system")
    for item in items:
        item.add_marker(skip)


@pytest.fixture(scope="session")
def api() -> Api:
    return Api(BASE_URL.rstrip("/"), ARCHIVE_DIR)


@pytest.fixture
def new_ree(api: Api, request: pytest.FixtureRequest) -> Iterator[Callable[..., str]]:
    """Create REEs on demand; each is downloaded, then released, when the test ends."""
    created: list[str] = []
    label = re.sub(r"[^a-z0-9]+", "-", request.node.name.lower()).strip("-")

    def create(name: str = label, **kwargs: str) -> str:
        ree_id: str = api.create(name[:60], **kwargs)
        created.append(ree_id)
        return ree_id

    yield create
    for ree_id in created:
        api.keep_archive(ree_id, label)
        api.release(ree_id)
