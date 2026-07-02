"""Manager control-plane behaviour against a fake agent client.

The runtime lives behind the ``AgentClient`` seam, so these tests drive the
manager with an in-memory fake — no Docker, no HTTP. They cover the control-plane
logic the manager owns: provisioning + init-ree + registry, frame routing during
dispatch, and translating a terminal ``unavailable`` frame into an error.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from repo2ree_protocol.agent import (
    AgentFrame,
    LocationFrame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
    WorkbenchLocation,
)
from repo2ree_protocol.command import WriteFileArgs, WriteFileCommand
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor import WorkbenchManager, WorkbenchRegistry, WorkbenchUnavailableError


class FakeAgent:
    """A programmable in-memory AgentClient."""

    def __init__(self) -> None:
        self.exec_simple_calls: list[tuple[str, list[str]]] = []
        self.query_returns: bytes = b"{}"
        self.action_frames: list[AgentFrame] = []
        self.running: bool = True
        # Records the agent_id each call was routed to, for placement assertions.
        self.routed_agent_ids: list[str] = []

    def resolve_agent(self, agent_id: str) -> str:
        # No registry here; placement resolves to whatever the caller requested.
        return agent_id

    def provision(self, agent_id: str, ree_id: str, image: str) -> Iterator[AgentFrame]:
        self.routed_agent_ids.append(agent_id)
        yield LogFrame(stream="system", level="info", message=f"pulling {image}")
        yield LocationFrame(
            location=WorkbenchLocation(container_name=f"repo2ree-wb-{ree_id}", volume_name=f"repo2ree-ree-{ree_id}")
        )

    def reprovision(self, agent_id: str, ree_id: str, location: WorkbenchLocation, image: str) -> Iterator[AgentFrame]:
        self.routed_agent_ids.append(agent_id)
        yield from ()

    def remove(self, agent_id: str, ree_id: str, location: WorkbenchLocation) -> None:
        self.routed_agent_ids.append(agent_id)

    def is_running(self, agent_id: str, container_name: str) -> bool:
        return self.running

    def exec_simple(self, agent_id: str, container_name: str, argv: list[str], timeout: int = 60) -> None:
        self.routed_agent_ids.append(agent_id)
        self.exec_simple_calls.append((container_name, argv))

    def exec_query(self, agent_id: str, container_name: str, argv: list[str], timeout: int = 30) -> bytes:
        self.routed_agent_ids.append(agent_id)
        return self.query_returns

    def exec_action(
        self, agent_id: str, container_name: str, cmd_json: str, run_id: str, env: dict[str, str]
    ) -> Iterator[AgentFrame]:
        self.routed_agent_ids.append(agent_id)
        yield from self.action_frames

    def copy_in(self, agent_id: str, container_name: str, source_path: str, container_path: str) -> None:
        self.routed_agent_ids.append(agent_id)


def _manager(tmp_path, agent: FakeAgent) -> WorkbenchManager:
    return WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="default:img",
        agent=agent,
    )


def test_provision_registers_handle_and_runs_init_ree(tmp_path) -> None:
    agent = FakeAgent()
    logs: list[tuple[str, str, str]] = []
    manager = _manager(tmp_path, agent)

    handle = manager.provision("ree1", name="My REE", log=lambda *e: logs.append(e))

    assert handle.container_name == "repo2ree-wb-ree1"
    assert handle.image == "default:img"
    # init-ree was issued against the freshly provisioned container.
    assert agent.exec_simple_calls == [
        ("repo2ree-wb-ree1", ["repo2ree-exec", "init-ree", "--ree-id", "ree1", "--name", "My REE"])
    ]
    # Provision log frames were forwarded to the sink.
    assert any("pulling default:img" in message for _, _, message in logs)
    # The handle is persisted.
    assert manager.is_registered("ree1")


def test_placement_pins_ree_to_chosen_agent(tmp_path) -> None:
    agent = FakeAgent()
    manager = _manager(tmp_path, agent)

    handle = manager.provision("ree1", name="My REE", agent_id="worker-2")

    # The chosen agent is recorded on the handle and persisted for affinity.
    assert handle.agent_id == "worker-2"
    looked_up = manager.lookup("ree1")
    assert looked_up is not None
    assert looked_up.agent_id == "worker-2"

    # Every later op is routed back to the owning agent, not an arbitrary one.
    agent.routed_agent_ids.clear()
    manager.get_ree_metadata(handle)
    cmd = WriteFileCommand(args=WriteFileArgs(path="p", content="c"))
    manager.dispatch_action(handle, cmd, "run1", lambda *e: None)
    manager.teardown(handle)
    assert set(agent.routed_agent_ids) == {"worker-2"}


def test_dispatch_action_routes_frames_and_returns_result(tmp_path) -> None:
    agent = FakeAgent()
    spans: list[list[str]] = []
    manager = WorkbenchManager(
        registry=WorkbenchRegistry(tmp_path / "registry.json"),
        workbench_image="default:img",
        agent=agent,
        span_sink=lambda payloads: spans.append(payloads),
    )
    handle = manager.provision("ree1", name="My REE")

    agent.action_frames = [
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
    agent = FakeAgent()
    manager = _manager(tmp_path, agent)
    handle = manager.provision("ree1", name="My REE")

    agent.action_frames = [UnavailableFrame(detail="container gone")]
    with pytest.raises(WorkbenchUnavailableError, match="container gone"):
        manager.dispatch_action(
            handle,
            WriteFileCommand(args=WriteFileArgs(path="a.txt", content="x")),
            "run1",
            lambda *_: None,
        )


def test_dispatch_action_without_result_frame_is_failure(tmp_path) -> None:
    agent = FakeAgent()
    manager = _manager(tmp_path, agent)
    handle = manager.provision("ree1", name="My REE")

    agent.action_frames = [LogFrame(stream="stdout", level="info", message="partial")]
    result = manager.dispatch_action(
        handle,
        WriteFileCommand(args=WriteFileArgs(path="a.txt", content="x")),
        "run1",
        lambda *_: None,
    )
    assert result.status == "failed"


def test_lookup_returns_none_when_not_running(tmp_path) -> None:
    agent = FakeAgent()
    manager = _manager(tmp_path, agent)
    manager.provision("ree1", name="My REE")

    agent.running = False
    assert manager.lookup("ree1") is None
