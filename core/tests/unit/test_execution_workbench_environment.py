"""What a step records it ran in: as the workbench states it, or the host the executor is on."""

from __future__ import annotations

import json

import pytest

from repo2ree_core.execution.workbench_environment import ENVIRONMENT_VARIABLE, observe_workbench_environment
from repo2ree_ree.workbench_environment import WorkbenchEnvironment

_DECLARED = WorkbenchEnvironment(kind="image", image="python:3.12-slim", needs_container_engine=True)
_DIGEST = "sha256:" + "a" * 64


def test_the_workbench_statement_is_recorded_under_the_declaration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        ENVIRONMENT_VARIABLE, json.dumps({"backend": "container", "image_digest": _DIGEST, "script_engine": "nested"})
    )

    observed = observe_workbench_environment(_DECLARED)

    assert (observed.declared, observed.backend, observed.image_digest, observed.script_engine) == (
        _DECLARED,
        "container",
        _DIGEST,
        "nested",
    )


@pytest.mark.parametrize("statement", ["", "not json", json.dumps({"backend": "container"})])
def test_without_a_readable_statement_the_executor_describes_its_host(
    monkeypatch: pytest.MonkeyPatch, statement: str
) -> None:
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, statement)

    observed = observe_workbench_environment(None)

    assert observed.backend == "host"
    assert observed.host is not None
    assert observed.host.os
    assert observed.host.arch
    assert observed.declared is None
