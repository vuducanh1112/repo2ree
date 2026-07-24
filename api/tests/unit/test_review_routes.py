from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api import reviews as review_routes
from repo2ree_api.deps import workbench_manager
from repo2ree_protocol.command import ReviewAcquireSourceCommand, ReviewBuildRuntimeCommand
from repo2ree_supervisor import WorkbenchHandle


def test_list_reviews_returns_persisted_attempts(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workbench_manager,
        "get_reviews",
        lambda handle: {
            "reviews": [
                {
                    "review_id": "review-one",
                    "created_at": "2026-07-24T10:00:00Z",
                    "updated_at": "2026-07-24T10:00:01Z",
                    "status": "completed",
                    "source_comparison": {
                        "policy": "swhid",
                        "expected_swhid": "swh:1:dir:" + "1" * 40,
                        "observed_swhid": "swh:1:dir:" + "1" * 40,
                        "verdict": "identical",
                    },
                }
            ]
        },
    )

    response = client.get(f"/api/v1/rees/{online_ree.ree_id}/reviews")

    assert response.status_code == 200
    assert response.json()["reviews"][0]["source_comparison"]["verdict"] == "identical"


def test_start_source_review_dispatches_review_command(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def start(ree_id: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"ree_id": ree_id, **kwargs})
        return {
            "run_id": "review-source-run",
            "ree_id": ree_id,
            "operation": "source",
            "status": "queued",
            "created_at": "2026-07-24T10:00:00Z",
            "started_at": None,
            "finished_at": None,
            "outputs": {},
            "failure": None,
        }

    monkeypatch.setattr(review_routes, "start_single_command_run", start)

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/source:reproduce",
        json={},
    )

    assert response.status_code == 200
    assert captured["ree_id"] == online_ree.ree_id
    assert captured["operation"] == "source"
    command = captured["command"]
    assert isinstance(command, ReviewAcquireSourceCommand)
    assert command.args.review_id.startswith("review-")
    assert captured["fallback_outputs"] == {"review_id": command.args.review_id}


def test_start_build_review_targets_the_named_attempt(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def start(ree_id: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"ree_id": ree_id, **kwargs})
        return {
            "run_id": "review-build-run",
            "ree_id": ree_id,
            "operation": "build",
            "status": "queued",
            "created_at": "2026-07-24T10:00:00Z",
            "started_at": None,
            "finished_at": None,
            "outputs": {},
            "failure": None,
        }

    monkeypatch.setattr(review_routes, "start_single_command_run", start)

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one/build:reproduce",
        json={},
    )

    assert response.status_code == 200
    assert captured["operation"] == "build"
    command = captured["command"]
    assert isinstance(command, ReviewBuildRuntimeCommand)
    # The build joins the attempt named in the path rather than opening a new one.
    assert command.args.review_id == "review-one"
    assert command.args.prune_workspace is True


def test_get_review_returns_one_attempt_and_404s_for_the_rest(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workbench_manager,
        "get_reviews",
        lambda handle: {
            "reviews": [
                {
                    "review_id": "review-one",
                    "created_at": "2026-07-24T10:00:00Z",
                    "updated_at": "2026-07-24T10:00:01Z",
                    "status": "completed",
                    "steps": [
                        {
                            "step": "build",
                            "status": "completed",
                            "started_at": "2026-07-24T10:00:00Z",
                            "updated_at": "2026-07-24T10:00:01Z",
                        }
                    ],
                    "build_comparison": {"policy": "sbom-closure", "verdict": "equivalent"},
                }
            ]
        },
    )

    found = client.get(f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one")
    assert found.status_code == 200
    assert found.json()["build_comparison"]["verdict"] == "equivalent"

    missing = client.get(f"/api/v1/rees/{online_ree.ree_id}/reviews/review-other")
    assert missing.status_code == 404
