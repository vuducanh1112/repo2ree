"""The script-lint endpoints.

``checkScriptDraft`` is the one covered in depth here: it is stateless and
needs no workbench, so it is exercised end to end. ``lintReeScripts`` binds a
workbench command, which the core handler tests already cover.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _draft(source: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"target": {"kind": "experiment_run", "experiment_name": "figure-3"}, "source": source}
    payload.update(extra)
    return payload


def test_a_draft_is_checked_without_any_ree(client: TestClient) -> None:
    # No ree_id in the path and none referenced: an editor can call this before
    # a workbench exists, which is the point of the route.
    resp = client.post("/api/v1/script-lints:draft", json=_draft('docker run img main.py | tee "out"\n'))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["target"]["path"] == "ree-scripts/experiments/figure-3.sh"
    assert "exit_status_masked_by_pipe" in {finding["code"] for finding in body["findings"]}


def test_a_draft_runs_only_the_contract_tier(client: TestClient) -> None:
    # The other two tiers spawn a process, which the control plane does not do.
    resp = client.post("/api/v1/script-lints:draft", json=_draft("set -eu\n"))
    assert resp.status_code == 200, resp.text
    assert [tier["tier"] for tier in resp.json()["tiers"]] == ["contract"]


def test_a_draft_is_graded_against_the_declarations_sent_with_it(client: TestClient) -> None:
    # An editor holds the path it is editing and nothing else — no digest, no
    # size. Those are derived server-side from the overlay file, so asking for
    # them here would mean asking the client to invent them.
    resp = client.post(
        "/api/v1/script-lints:draft",
        json=_draft("docker run img main.py\n", declarations={"runtime_path": "runtime.tar"}),
    )
    assert resp.status_code == 200, resp.text
    assert "runtime_not_referenced" in {finding["code"] for finding in resp.json()["findings"]}


def test_a_draft_rejects_declarations_it_does_not_read(client: TestClient) -> None:
    # The declaration surface is an explicit part of the contract, so a field
    # no rule consults is a mistake worth reporting rather than ignoring.
    resp = client.post(
        "/api/v1/script-lints:draft",
        json=_draft("set -eu\n", declarations={"build_runtime_script_size": 0}),
    )
    assert resp.status_code == 422, resp.text


def test_a_draft_with_no_declarations_makes_no_claims_about_them(client: TestClient) -> None:
    resp = client.post("/api/v1/script-lints:draft", json=_draft("docker run img main.py\n"))
    assert resp.status_code == 200, resp.text
    assert "runtime_not_referenced" not in {finding["code"] for finding in resp.json()["findings"]}


def test_lint_never_refuses_a_script_it_dislikes(client: TestClient) -> None:
    # Advice, not a gate: a report full of findings is still a 200 with ok true.
    resp = client.post("/api/v1/script-lints:draft", json=_draft('set --\nrun | tee "x"\n'))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["findings"]) >= 2
    assert all(finding["blocking"] is False for finding in body["findings"])


def test_an_experiment_target_without_a_name_is_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/script-lints:draft",
        json={"target": {"kind": "experiment_run"}, "source": "set -eu\n"},
    )
    assert resp.status_code == 422, resp.text
