"""A new REE declares what its scripts run in as soon as its store has created it."""

from __future__ import annotations

from typing import Any

import pytest

from repo2ree_api.control import rees
from repo2ree_api.deps import command_dispatcher
from repo2ree_protocol.command import PatchReeDefinitionCommand
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.environment import EnvironmentDefinition
from repo2ree_supervisor import ReeRoute

PINNED = "docker.io/library/docker@sha256:" + "a" * 64


def _declared(
    monkeypatch: pytest.MonkeyPatch, environment: EnvironmentDefinition, result: ActionResult
) -> tuple[Any, list[str]]:
    sent: list[PatchReeDefinitionCommand] = []
    logged: list[str] = []

    def dispatch(handle: ReeRoute, command: PatchReeDefinitionCommand, run_id: str, log: object) -> ActionResult:
        sent.append(command)
        return result

    monkeypatch.setattr(command_dispatcher, "dispatch_action", dispatch)
    handle = ReeRoute(ree_id="ree-1", workbench_id="wb-1", store_id="lab-1")
    rees._declare_environment(
        handle, "run-1", lambda stream, level, message: logged.append(f"{level}: {message}"), environment
    )
    return sent[0].args.patch, logged


def test_an_ree_declares_the_image_its_store_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    patch, logged = _declared(
        monkeypatch, EnvironmentDefinition(kind="image", image=PINNED), ActionResult(status="succeeded")
    )

    assert patch == {"environment": {"kind": "image", "image": PINNED, "needs_container_engine": False}}
    assert logged == []


def test_a_declaration_that_will_not_record_is_said_and_does_not_fail_the_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, logged = _declared(
        monkeypatch, EnvironmentDefinition(kind="host"), ActionResult.failed("conflict", "version moved")
    )

    assert logged == ["warn: The REE's environment was not recorded: version moved"]
