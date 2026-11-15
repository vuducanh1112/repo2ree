"""The script-lint endpoints.

``checkScriptDraft`` asks the REE's workbench to run ``ree lint-draft``; what the
checks find is the CLI's to test (cli/tests/unit/test_authoring_verbs.py). Here:
what the route sends there, and what it refuses before sending anything.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from repo2ree_api.deps import command_dispatcher
from repo2ree_protocol.command import ScriptTarget, ScriptTargetSelectorArg
from repo2ree_protocol.lint import LintReport, ScriptDeclarations
from repo2ree_supervisor import ReeRoute


def _draft(source: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"target": {"kind": "experiment_run", "experiment_name": "figure-3"}, "source": source}
    payload.update(extra)
    return payload


@pytest.fixture
def sent(online_ree: ReeRoute, monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def lint_draft(
        handle: ReeRoute, target: ScriptTargetSelectorArg, source: str, declarations: ScriptDeclarations
    ) -> LintReport:
        calls.append((handle, target, source, declarations))
        return LintReport(engine_version="1", target=ScriptTarget(kind=target.kind, path="ree-scripts/x.sh"))

    monkeypatch.setattr(command_dispatcher, "lint_draft", lint_draft)
    return calls


def test_a_draft_goes_to_the_rees_workbench(
    client: TestClient, online_ree: ReeRoute, sent: list[tuple[Any, ...]]
) -> None:
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/script-lints:draft",
        json=_draft("set -eu\n", declarations={"experiment_environment_path": "runtime.tar"}),
    )

    assert resp.status_code == 200, resp.text
    assert sent == [
        (
            online_ree,
            ScriptTargetSelectorArg(kind="experiment_run", experiment_name="figure-3"),
            "set -eu\n",
            ScriptDeclarations(experiment_environment_path="runtime.tar"),
        )
    ]


def test_a_draft_rejects_declarations_it_does_not_read(
    client: TestClient, online_ree: ReeRoute, sent: list[tuple[Any, ...]]
) -> None:
    # The declaration surface is an explicit part of the contract, so a field
    # no rule consults is a mistake worth reporting rather than ignoring.
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/script-lints:draft",
        json=_draft("set -eu\n", declarations={"build_experiment_environment_script_size": 0}),
    )
    assert resp.status_code == 422, resp.text
    assert sent == []


def test_an_experiment_target_without_a_name_is_rejected(
    client: TestClient, online_ree: ReeRoute, sent: list[tuple[Any, ...]]
) -> None:
    resp = client.post(
        f"/api/v1/rees/{online_ree.ree_id}/script-lints:draft",
        json={"target": {"kind": "experiment_run"}, "source": "set -eu\n"},
    )
    assert resp.status_code == 422, resp.text
    assert sent == []


def test_a_draft_for_an_unknown_ree_is_not_found(client: TestClient) -> None:
    assert client.post("/api/v1/rees/no-such-ree/script-lints:draft", json=_draft("set -eu\n")).status_code == 404
