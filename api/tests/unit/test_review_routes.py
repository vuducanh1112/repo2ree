from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api import reviews as review_routes
from repo2ree_api.deps import workbench_manager
from repo2ree_protocol.command import (
    ReviewAcquireSourceCommand,
    ReviewActivationTestCommand,
    ReviewBuildRuntimeCommand,
    ReviewRunExperimentCommand,
)
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
    assert command.args.basis == "auto"
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
    # The rebuilt workspace survives by default: activation runs in it, and on an
    # independent basis the runtime it holds exists nowhere else.
    assert command.args.prune_workspace is False
    assert command.args.basis == "auto"


def test_start_activation_review_targets_the_named_attempt(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def start(ree_id: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"ree_id": ree_id, **kwargs})
        return {
            "run_id": "review-activation-run",
            "ree_id": ree_id,
            "operation": "activation",
            "status": "queued",
            "created_at": "2026-07-24T10:00:00Z",
            "started_at": None,
            "finished_at": None,
            "outputs": {},
            "failure": None,
        }

    monkeypatch.setattr(review_routes, "start_single_command_run", start)

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one/activation:reproduce",
        json={},
    )

    assert response.status_code == 200
    assert captured["operation"] == "activation"
    command = captured["command"]
    assert isinstance(command, ReviewActivationTestCommand)
    assert command.args.review_id == "review-one"


def test_activation_takes_no_basis_at_the_edge(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Activation inherits what the attempt's evidence is worth rather than
    choosing, so offering the knob here would be offering a lie."""
    monkeypatch.setattr(review_routes, "start_single_command_run", lambda *a, **k: {})

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one/activation:reproduce",
        json={"basis": "independent"},
    )

    assert response.status_code == 422


def test_start_experiment_review_names_both_the_attempt_and_the_experiment(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def start(ree_id: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"ree_id": ree_id, **kwargs})
        return {
            "run_id": "review-experiment-run",
            "ree_id": ree_id,
            "operation": "experiment",
            "status": "queued",
            "created_at": "2026-07-24T10:00:00Z",
            "started_at": None,
            "finished_at": None,
            "outputs": {},
            "failure": None,
        }

    monkeypatch.setattr(review_routes, "start_single_command_run", start)

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one/experiments/headline result:reproduce",
        json={},
    )

    assert response.status_code == 200
    assert captured["operation"] == "experiment"
    command = captured["command"]
    assert isinstance(command, ReviewRunExperimentCommand)
    assert command.args.review_id == "review-one"
    # Names may carry spaces, so the route has to survive a percent-encoded one.
    assert command.args.experiment_name == "headline result"


def test_experiment_review_takes_no_basis_at_the_edge(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Like activation, the run inherits what the workspace it happens in is
    worth rather than choosing a basis of its own."""
    monkeypatch.setattr(review_routes, "start_single_command_run", lambda *a, **k: {})

    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one/experiments/one:reproduce",
        json={"basis": "independent"},
    )

    assert response.status_code == 422


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


def test_a_requested_basis_reaches_the_workbench_command(
    client: TestClient,
    online_ree: WorkbenchHandle,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproducing from the REE's own artifacts is a per-run choice, so it has
    to survive the trip from the request body into the dispatched command."""
    captured: dict[str, Any] = {}

    def start(ree_id: str, **kwargs: Any) -> dict[str, Any]:
        captured.update({"ree_id": ree_id, **kwargs})
        return {
            "run_id": "review-run",
            "ree_id": ree_id,
            "operation": kwargs["operation"],
            "status": "queued",
            "created_at": "2026-07-24T10:00:00Z",
            "started_at": None,
            "finished_at": None,
            "outputs": {},
            "failure": None,
        }

    monkeypatch.setattr(review_routes, "start_single_command_run", start)

    source = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/source:reproduce",
        json={"basis": "bundled"},
    )
    assert source.status_code == 200
    assert captured["command"].args.basis == "bundled"

    build = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/review-one/build:reproduce",
        json={"basis": "bundled"},
    )
    assert build.status_code == 200
    assert captured["command"].args.basis == "bundled"


def test_an_unknown_basis_is_rejected_at_the_edge(
    client: TestClient,
    online_ree: WorkbenchHandle,
) -> None:
    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/source:reproduce",
        json={"basis": "whatever"},
    )

    assert response.status_code == 422


def test_starting_a_source_review_names_the_attempt_it_opened(
    client: TestClient,
    online_ree: WorkbenchHandle,
) -> None:
    """The POST answers "which attempt did I just open?" on its own.

    Not deferred to the run's completion, and not inferrable from the reviews
    list: the workbench writes the attempt's record a moment after this returns,
    so a client that reached for the newest listed attempt in between would
    address the *previous* one and silently certify the wrong evidence.
    """
    response = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/reviews/source:reproduce",
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    # Asserted without pinning the status: the run may already have started by
    # the time this is serialized, and the point is that the id does not wait on
    # it either way.
    assert body["outputs"]["review_id"].startswith("review-")
