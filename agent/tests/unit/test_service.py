from __future__ import annotations

from collections.abc import Iterator

import pytest

from repo2ree_agent.service import WorkbenchService
from repo2ree_protocol.agent import AgentFrame, DockerWorkbenchSpec, DoneFrame, WorkbenchRef


class _Runtime:
    runtime_name = "docker"

    def provision(self, ree_id: str, spec: DockerWorkbenchSpec) -> Iterator[AgentFrame]:
        yield DoneFrame()


def test_service_routes_provision_by_spec_runtime() -> None:
    runtime = _Runtime()
    service = WorkbenchService({runtime.runtime_name: runtime})  # type: ignore[dict-item]

    assert list(service.provision("ree-1", DockerWorkbenchSpec(base_image="ubuntu:24.04"))) == [DoneFrame()]


def test_service_rejects_unknown_reference_runtime() -> None:
    service = WorkbenchService({})

    with pytest.raises(ValueError, match="unsupported workbench runtime"):
        service.is_running(WorkbenchRef(runtime="slurm", token="opaque"))  # noqa: S106
