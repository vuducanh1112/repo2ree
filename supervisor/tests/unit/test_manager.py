"""Manager control-plane behaviour against a fake workbench client.

The runtime lives behind the ``ProviderClient``/``WorkbenchClient`` seams, so
these tests drive the manager with an in-memory fake serving both — no Docker, no HTTP. They cover the control-plane
logic the manager owns: provisioning + init-ree + registry, frame routing during
dispatch, and translating a terminal ``unavailable`` frame into an error.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from repo2ree_protocol.command import WriteFileArgs, WriteFileCommand
from repo2ree_protocol.frames import (
    Frame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
    WorkbenchRef,
    WorkbenchRefFrame,
)
from repo2ree_protocol.provider import WorkbenchSpec
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchManager, WorkbenchRegistry, WorkbenchUnavailableError


class FakeWorkbenchClient:
    """A programmable in-memory fake implementing both client seams."""

    def __init__(self) -> None:
        self.exec_simple_calls: list[tuple[str, list[str]]] = []
        self.query_returns: bytes = b"{}"
        self.action_frames: list[Frame] = []
        self.running: bool = True
        self.cancel_run_calls: list[tuple[str, str]] = []
        # Records the workbench_id each call was routed to, for placement assertions.
        self.routed_workbench_ids: list[str] = []
        self.fail_init = False
        self.fail_remove = False
        self.best_effort_remove_calls: list[str] = []

    def resolve_provider(self, provider_id: str) -> str:
        # Mirror the real registry: an empty provision-time preference resolves
        # to a concrete connected service before placement is persisted.
        return provider_id or "provider-1"

    def provision(
        self,
        provider_id: str,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: WorkbenchSpec,
    ) -> Iterator[Frame]:
        self.routed_workbench_ids.append(provider_id)
        yield LogFrame(stream="system", level="info", message=f"pulling {spec.base_image}")
        yield WorkbenchRefFrame(ref=WorkbenchRef(runtime="docker", token=ree_id))

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        self.routed_workbench_ids.append(workbench_id)

    def reserve_external(self, allocation_id: str, workbench_id: str | None = None) -> str:
        resolved = workbench_id or "external-1"
        self.routed_workbench_ids.append(resolved)
        return resolved

    def release_reservation(self, workbench_id: str, allocation_id: str) -> None:
        self.routed_workbench_ids.append(workbench_id)

    def bind(self, workbench_id: str, allocation_id: str, ree_id: str) -> None:
        self.routed_workbench_ids.append(workbench_id)

    def remove(self, workbench_id: str, ref: WorkbenchRef) -> None:
        self.routed_workbench_ids.append(workbench_id)
        if self.fail_remove:
            raise RuntimeError("remove failed")

    def remove_best_effort(self, workbench_id: str, ref: WorkbenchRef) -> bool:
        self.routed_workbench_ids.append(workbench_id)
        self.best_effort_remove_calls.append(ref.token)
        return True

    def is_running(self, workbench_id: str, ref: WorkbenchRef) -> bool:
        return self.running

    def is_connected(self, workbench_id: str) -> bool:
        return self.running

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        self.routed_workbench_ids.append(workbench_id)
        self.exec_simple_calls.append((workbench_id, argv))
        if self.fail_init and argv and argv[0] == "init-ree":
            raise RuntimeError("init failed")

    def exec_query(self, workbench_id: str, argv: list[str], timeout: int = 30) -> bytes:
        self.routed_workbench_ids.append(workbench_id)
        return self.query_returns

    def exec_query_stream(self, workbench_id: str, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        self.routed_workbench_ids.append(workbench_id)
        yield self.query_returns

    def exec_action(self, workbench_id: str, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]:
        self.routed_workbench_ids.append(workbench_id)
        yield from self.action_frames

    def cancel_run(self, workbench_id: str, run_id: str) -> None:
        self.routed_workbench_ids.append(workbench_id)
        self.cancel_run_calls.append((workbench_id, run_id))

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str) -> None:
        self.routed_workbench_ids.append(workbench_id)

    def drain(self, workbench_id: str) -> None:
        self.routed_workbench_ids.append(workbench_id)


def _manager(tmp_path, workbench: FakeWorkbenchClient) -> WorkbenchManager:
    return WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="default:img",
        provider=workbench,
        workbench=workbench,
    )


def test_provision_registers_handle_and_runs_init_ree(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    logs: list[tuple[str, str, str]] = []
    manager = _manager(tmp_path, workbench)

    handle = manager.provision("ree1", name="My REE", log=lambda *e: logs.append(e))

    assert handle.ref == WorkbenchRef(runtime="docker", token="ree1")  # noqa: S106
    assert handle.image == "default:img"
    # init-ree was issued against the freshly provisioned opaque reference.
    assert workbench.exec_simple_calls == [(handle.workbench_id, ["init-ree", "--name", "My REE"])]
    # Provision log frames were forwarded to the sink.
    assert any("pulling default:img" in message for _, _, message in logs)
    # The handle is persisted.
    assert manager.is_registered("ree1")


def test_external_workbench_is_reserved_bound_and_released_without_provider_remove(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)

    handle = manager.reserve_external("ree-external", "External REE", "external-1")

    assert handle.mode == "external"
    assert handle.provider_id == ""
    assert handle.workbench_id == "external-1"
    assert workbench.exec_simple_calls == [("external-1", ["init-ree", "--name", "External REE"])]

    workbench.routed_workbench_ids.clear()
    manager.teardown(handle)
    assert workbench.routed_workbench_ids == ["external-1", "external-1"]


def test_placement_pins_ree_to_chosen_workbench(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)

    handle = manager.provision("ree1", name="My REE", provider_id="worker-2")

    # The chosen workbench is recorded on the handle and persisted for affinity.
    assert handle.provider_id == "worker-2"
    assert handle.workbench_id.startswith("wb-")
    looked_up = manager.lookup("ree1")
    assert looked_up is not None
    assert looked_up.workbench_id == handle.workbench_id
    assert looked_up.provider_id == "worker-2"

    # Every later op is routed back to the owning workbench, not an arbitrary one.
    workbench.routed_workbench_ids.clear()
    manager.get_ree_manifest(handle)
    cmd = WriteFileCommand(args=WriteFileArgs(path="p", content="c"))
    manager.dispatch_action(handle, cmd, "run1", lambda *e: None)
    manager.teardown(handle)
    assert set(workbench.routed_workbench_ids) == {"worker-2", handle.workbench_id}


def test_dispatch_action_routes_frames_and_returns_result(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    spans: list[list[str]] = []
    manager = WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="default:img",
        provider=workbench,
        workbench=workbench,
        span_sink=lambda payloads: spans.append(payloads),
    )
    handle = manager.provision("ree1", name="My REE")

    workbench.action_frames = [
        LogFrame(stream="stdout", level="info", message="working"),
        SpanFrame(payload='{"name": "op"}'),
        ResultFrame(result=ActionResult(status="succeeded", outputs={"k": "v"})),
    ]
    logs: list[tuple[str, str, str]] = []
    result = manager.dispatch_action(
        handle,
        WriteFileCommand(args=WriteFileArgs(path="a.txt", content="x")),
        "run1",
        lambda *e: logs.append(e),
    )

    assert result.status == "succeeded"
    assert result.outputs == {"k": "v"}
    assert ("stdout", "info", "working") in logs
    assert spans == [['{"name": "op"}']]


def test_dispatch_action_raises_on_unavailable_frame(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)
    handle = manager.provision("ree1", name="My REE")

    workbench.action_frames = [UnavailableFrame(detail="container gone")]
    with pytest.raises(WorkbenchUnavailableError, match="container gone"):
        manager.dispatch_action(
            handle,
            WriteFileCommand(args=WriteFileArgs(path="a.txt", content="x")),
            "run1",
            lambda *_: None,
        )


def test_dispatch_action_without_result_frame_is_failure(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)
    handle = manager.provision("ree1", name="My REE")

    workbench.action_frames = [LogFrame(stream="stdout", level="info", message="partial")]
    result = manager.dispatch_action(
        handle,
        WriteFileCommand(args=WriteFileArgs(path="a.txt", content="x")),
        "run1",
        lambda *_: None,
    )
    assert result.status == "failed"


def test_cancel_run_routes_to_pinned_workbench(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)
    handle = manager.provision("ree1", name="My REE", provider_id="worker-2")

    workbench.routed_workbench_ids.clear()
    manager.cancel_run(handle, "run-7")

    assert workbench.cancel_run_calls == [(handle.workbench_id, "run-7")]
    assert workbench.routed_workbench_ids == [handle.workbench_id]


def test_lookup_returns_none_when_not_running(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)
    manager.provision("ree1", name="My REE")

    workbench.running = False
    assert manager.lookup("ree1") is None


def test_provision_compensates_when_initialization_fails(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    workbench.fail_init = True
    manager = _manager(tmp_path, workbench)

    with pytest.raises(RuntimeError, match="init failed"):
        manager.provision("ree1", name="My REE")

    assert workbench.best_effort_remove_calls == ["ree1"]
    assert not manager.is_registered("ree1")


def test_teardown_keeps_registry_entry_when_remote_remove_fails(tmp_path) -> None:
    workbench = FakeWorkbenchClient()
    manager = _manager(tmp_path, workbench)
    handle = manager.provision("ree1", name="My REE")
    workbench.fail_remove = True

    with pytest.raises(RuntimeError, match="remove failed"):
        manager.teardown(handle)

    assert manager.is_registered("ree1")
