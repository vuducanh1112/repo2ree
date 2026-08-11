from __future__ import annotations

from collections.abc import Iterator

import pytest

from repo2ree_agent.service import WorkbenchService
from repo2ree_protocol.agent import AgentFrame, DockerWorkbenchSpec, DoneFrame, WorkbenchRef


class _Runtime:
    runtime_name = "docker"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def provision(self, ree_id: str, spec: DockerWorkbenchSpec) -> Iterator[AgentFrame]:
        self.calls.append("provision")
        yield DoneFrame()

    def reprovision(self, ref: WorkbenchRef, spec: DockerWorkbenchSpec) -> Iterator[AgentFrame]:
        self.calls.append("reprovision")
        yield DoneFrame()

    def remove(self, ref: WorkbenchRef) -> None:
        self.calls.append("remove")

    def is_running(self, ref: WorkbenchRef) -> bool:
        self.calls.append("is_running")
        return True

    def exec_action(self, ref: WorkbenchRef, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[AgentFrame]:
        self.calls.append("exec_action")
        yield DoneFrame()

    def exec_simple(self, ref: WorkbenchRef, argv: list[str], timeout: int = 60) -> None:
        self.calls.append("exec_simple")

    def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        self.calls.append("exec_query")
        yield b"result"

    def cancel_run(self, ref: WorkbenchRef, run_id: str) -> None:
        self.calls.append("cancel_run")

    def copy_in(self, ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        self.calls.append("copy_in")


def test_service_routes_provision_by_spec_runtime() -> None:
    runtime = _Runtime()
    service = WorkbenchService({runtime.runtime_name: runtime})

    assert list(service.provision("ree-1", DockerWorkbenchSpec(base_image="ubuntu:24.04"))) == [DoneFrame()]


def test_service_routes_every_reference_operation() -> None:
    runtime = _Runtime()
    service = WorkbenchService({runtime.runtime_name: runtime})
    ref = WorkbenchRef(runtime="docker", token="opaque")  # noqa: S106
    spec = DockerWorkbenchSpec(base_image="ubuntu:24.04")

    assert list(service.reprovision(ref, spec)) == [DoneFrame()]
    service.remove(ref)
    assert service.is_running(ref) is True
    assert list(service.exec_action(ref, "{}", "run-1", {})) == [DoneFrame()]
    service.exec_simple(ref, ["doctor"])
    assert list(service.exec_query_stream(ref, ["archive"])) == [b"result"]
    service.cancel_run(ref, "run-1")
    service.copy_in(ref, "source", "/ree/dest")

    assert runtime.calls == [
        "reprovision",
        "remove",
        "is_running",
        "exec_action",
        "exec_simple",
        "exec_query",
        "cancel_run",
        "copy_in",
    ]


def test_service_rejects_cross_runtime_reprovision() -> None:
    runtime = _Runtime()
    service = WorkbenchService({runtime.runtime_name: runtime})
    ref = WorkbenchRef(runtime="slurm", token="opaque")  # noqa: S106

    with pytest.raises(ValueError, match="cannot reprovision"):
        list(service.reprovision(ref, DockerWorkbenchSpec(base_image="ubuntu:24.04")))


def test_service_rejects_unknown_reference_runtime() -> None:
    service = WorkbenchService({})

    with pytest.raises(ValueError, match="unsupported workbench runtime"):
        service.is_running(WorkbenchRef(runtime="slurm", token="opaque"))  # noqa: S106
