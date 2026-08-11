from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any, cast

from repo2ree_agent.control.dispatcher import dispatch_request
from repo2ree_agent.control.transfers import TransferStore
from repo2ree_agent.service import WorkbenchService
from repo2ree_protocol.agent import (
    AgentFrame,
    CancelRunRequest,
    CopyAbortRequest,
    CopyChunkRequest,
    CopyCloseRequest,
    CopyOpenRequest,
    DockerWorkbenchSpec,
    DoneFrame,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    IsRunningRequest,
    LogFrame,
    ProvisionRequest,
    RemoveRequest,
    ReprovisionRequest,
    TransferFrame,
    WorkbenchRef,
)

_REF = WorkbenchRef(runtime="docker", token="workbench")  # noqa: S106
_SPEC = DockerWorkbenchSpec(base_image="ubuntu:24.04")


class _Service:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.copied = b""

    def provision(self, ree_id: str, spec: DockerWorkbenchSpec):
        self.calls.append(("provision", ree_id, spec))
        yield LogFrame(stream="system", level="info", message="provisioned")

    def reprovision(self, ref: WorkbenchRef, spec: DockerWorkbenchSpec):
        self.calls.append(("reprovision", ref, spec))
        yield DoneFrame()

    def exec_action(self, ref: WorkbenchRef, cmd_json: str, run_id: str, env: dict[str, str]):
        self.calls.append(("exec_action", ref, cmd_json, run_id, env))
        yield DoneFrame()

    def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int):
        self.calls.append(("exec_query", ref, argv, timeout))
        yield b"query-result"

    def cancel_run(self, ref: WorkbenchRef, run_id: str) -> None:
        self.calls.append(("cancel_run", ref, run_id))

    def is_running(self, ref: WorkbenchRef) -> bool:
        self.calls.append(("is_running", ref))
        return True

    def exec_simple(self, ref: WorkbenchRef, argv: list[str], timeout: int) -> None:
        self.calls.append(("exec_simple", ref, argv, timeout))

    def remove(self, ref: WorkbenchRef) -> None:
        self.calls.append(("remove", ref))

    def copy_in(self, ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        self.calls.append(("copy_in", ref, workbench_path))
        self.copied = Path(source_path).read_bytes()


class _Harness:
    def __init__(self) -> None:
        self.service = _Service()
        self.transfers = TransferStore()
        self.frames: list[AgentFrame] = []
        self.byte_results: list[bytes] = []
        self.received: list[int] = []

    async def dispatch(self, request: Any) -> None:
        async def send(frame: AgentFrame) -> None:
            self.frames.append(frame)

        async def pump(factory: Any) -> None:
            self.frames.extend(factory())

        async def pump_bytes(factory: Any) -> None:
            self.byte_results.extend(factory())

        await dispatch_request(
            request,
            cast(WorkbenchService, self.service),
            self.transfers,
            send=send,
            pump=pump,
            pump_bytes=pump_bytes,
            record_received=self.received.append,
        )


def test_dispatcher_routes_streaming_requests() -> None:
    harness = _Harness()

    async def scenario() -> None:
        await harness.dispatch(ProvisionRequest(ree_id="ree-1", spec=_SPEC))
        await harness.dispatch(ReprovisionRequest(ref=_REF, spec=_SPEC))
        await harness.dispatch(ExecActionRequest(ref=_REF, cmd_json="{}", run_id="run-1", env={"TRACE_RELAY": "1"}))
        await harness.dispatch(ExecQueryRequest(ref=_REF, argv=["archive"], timeout=12))

    asyncio.run(scenario())

    assert [call[0] for call in harness.service.calls] == ["provision", "reprovision", "exec_action", "exec_query"]
    assert [frame.type for frame in harness.frames] == ["log", "done", "done"]
    assert harness.byte_results == [b"query-result"]


def test_dispatcher_routes_simple_requests_and_terminal_frames() -> None:
    harness = _Harness()

    async def scenario() -> None:
        await harness.dispatch(CancelRunRequest(ref=_REF, run_id="run-1"))
        await harness.dispatch(IsRunningRequest(ref=_REF))
        await harness.dispatch(ExecSimpleRequest(ref=_REF, argv=["doctor"], timeout=7))
        await harness.dispatch(RemoveRequest(ref=_REF))

    asyncio.run(scenario())

    assert [call[0] for call in harness.service.calls] == ["cancel_run", "is_running", "exec_simple", "remove"]
    assert [frame.type for frame in harness.frames] == ["done", "running", "done", "done"]


def test_dispatcher_reassembles_close_and_aborts_copy_transfers() -> None:
    harness = _Harness()

    async def scenario() -> None:
        await harness.dispatch(CopyOpenRequest(ref=_REF, workbench_path="/ree/input.bin"))
        transfer = cast(TransferFrame, harness.frames.pop()).transfer_id
        payload = b"transferred"
        await harness.dispatch(
            CopyChunkRequest(transfer_id=transfer, offset=0, data_b64=base64.b64encode(payload).decode())
        )
        await harness.dispatch(CopyCloseRequest(transfer_id=transfer))

        await harness.dispatch(CopyOpenRequest(ref=_REF, workbench_path="/ree/aborted.bin"))
        aborted = cast(TransferFrame, harness.frames.pop()).transfer_id
        await harness.dispatch(CopyAbortRequest(transfer_id=aborted))

    asyncio.run(scenario())

    assert harness.service.copied == b"transferred"
    assert harness.received == [len(b"transferred")]
    assert [frame.type for frame in harness.frames] == ["done", "done", "done"]
