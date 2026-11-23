from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from repo2ree_testbed.artifacts import service_dir

TEST_RESULTS_DIR = service_dir("api-unit")

_state_dir = Path(tempfile.mkdtemp(prefix="repo2ree-api-utest-"))
os.environ["UPLOAD_STAGING_DIR"] = str(_state_dir / "upload-staging")
os.environ["CONTROL_STATE_DIR"] = str(_state_dir / "control")
os.environ["REE_INDEX_FILE"] = str(_state_dir / "ree-index.json")
os.environ["RUN_REGISTRY_DIR"] = str(_state_dir / "runs")
os.environ["BEHAVIOUR_JOURNAL_DIR"] = str(_state_dir / "journal")

_claimed = os.environ.get("_REPO2REE_TRACE_TIER")
if _claimed and _claimed != "api-unit":
    raise RuntimeError(
        f"Both {_claimed} and api-unit tiers loaded in one pytest process; their spans "
        "collide on OpenTelemetry's set-once global provider. Run them separately: "
        "`just test-unit-package api` / `just test-integration-package api`, or `pytest api/tests/unit` "
        "and `pytest api/tests/integration`."
    )
os.environ["_REPO2REE_TRACE_TIER"] = "api-unit"

if "TRACE_FILE" not in os.environ:
    _trace_file = TEST_RESULTS_DIR / "traces.ndjson"
    os.environ["TRACE_FILE"] = str(_trace_file)
    _trace_file.parent.mkdir(parents=True, exist_ok=True)
    _trace_file.unlink(missing_ok=True)

from fastapi.testclient import TestClient  # noqa: E402

from repo2ree_api.deps import ree_router  # noqa: E402
from repo2ree_api.main import app  # noqa: E402
from repo2ree_supervisor import ReeRoute  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def online_ree(monkeypatch: pytest.MonkeyPatch) -> ReeRoute:
    ree_id = uuid4().hex
    handle = ReeRoute(ree_id=ree_id, workbench_id=f"wb-{ree_id}", store_id="lab-test")
    real_route = ree_router.route
    monkeypatch.setattr(ree_router, "route", lambda rid: handle if rid == ree_id else real_route(rid))
    return handle


@pytest.fixture
def staging_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from repo2ree_api.settings import service_settings

    staging = tmp_path / "upload-staging"
    monkeypatch.setattr(service_settings, "UPLOAD_STAGING_DIR", staging)
    return staging
