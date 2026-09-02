from __future__ import annotations

from collections.abc import Iterator

import pytest

from repo2ree_protocol.frames import DoneFrame, Frame, WorkbenchRef
from repo2ree_protocol.provider import DockerWorkbenchSpec
from repo2ree_provider_docker.provisioner import ProvisionerService


class _Backend:
    runtime_name = "docker"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def provision(
        self,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: DockerWorkbenchSpec,
    ) -> Iterator[Frame]:
        self.calls.append("provision")
        yield DoneFrame()

    def remove(self, ref: WorkbenchRef) -> None:
        self.calls.append("remove")

    def is_running(self, ref: WorkbenchRef) -> bool:
        self.calls.append("is_running")
        return True


def test_provisioner_routes_provision_by_spec_runtime() -> None:
    backend = _Backend()
    provisioner = ProvisionerService({backend.runtime_name: backend})

    assert list(
        provisioner.provision("alloc-1", "wb-1", "token", "ree-1", DockerWorkbenchSpec(base_image="ubuntu:24.04"))
    ) == [DoneFrame()]


def test_provisioner_routes_every_reference_operation() -> None:
    backend = _Backend()
    provisioner = ProvisionerService({backend.runtime_name: backend})
    ref = WorkbenchRef(runtime="docker", token="opaque")  # noqa: S106

    provisioner.remove(ref)
    assert provisioner.is_running(ref) is True

    assert backend.calls == ["remove", "is_running"]


def test_provisioner_rejects_unknown_reference_runtime() -> None:
    provisioner = ProvisionerService({})

    with pytest.raises(ValueError, match="unsupported workbench runtime"):
        provisioner.is_running(WorkbenchRef(runtime="slurm", token="opaque"))  # noqa: S106
