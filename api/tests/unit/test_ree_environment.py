"""A new REE declares what its scripts run in as soon as its workbench is set up."""

from __future__ import annotations

from typing import Any

import pytest

from repo2ree_api.control import rees
from repo2ree_api.deps import workbench_manager
from repo2ree_protocol.command import PatchReeDefinitionCommand
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchHandle

PINNED = "docker.io/library/docker@sha256:" + "a" * 64


def _declared(monkeypatch: pytest.MonkeyPatch, handle: WorkbenchHandle, result: ActionResult) -> tuple[Any, list[str]]:
    sent: list[PatchReeDefinitionCommand] = []
    logged: list[str] = []

    def dispatch(handle: WorkbenchHandle, command: PatchReeDefinitionCommand, run_id: str, log: object) -> ActionResult:
        sent.append(command)
        return result

    monkeypatch.setattr(workbench_manager, "dispatch_action", dispatch)
    rees._declare_environment(handle, "run-1", lambda stream, level, message: logged.append(f"{level}: {message}"))
    return sent[0].args.patch, logged


def test_a_provisioned_bench_declares_its_image(monkeypatch: pytest.MonkeyPatch) -> None:
    handle = WorkbenchHandle(ree_id="ree-1", mode="provider_managed", image=PINNED)

    patch, logged = _declared(monkeypatch, handle, ActionResult(status="succeeded"))

    assert patch == {"environment": {"kind": "image", "image": PINNED, "needs_container_engine": False}}
    assert logged == []


def test_an_external_workbench_declares_its_host(monkeypatch: pytest.MonkeyPatch) -> None:
    handle = WorkbenchHandle(ree_id="ree-1", mode="external")

    patch, _ = _declared(monkeypatch, handle, ActionResult(status="succeeded"))

    assert patch == {"environment": {"kind": "host", "image": None, "needs_container_engine": False}}


def test_a_declaration_that_will_not_record_is_said_and_does_not_fail_the_provision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handle = WorkbenchHandle(ree_id="ree-1", mode="provider_managed", image=PINNED)

    _, logged = _declared(monkeypatch, handle, ActionResult.failed("conflict", "version moved"))

    assert logged == ["warn: The REE's environment was not recorded: version moved"]
