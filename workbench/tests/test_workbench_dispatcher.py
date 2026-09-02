from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any, cast

from repo2ree_protocol.frames import DoneFrame, Frame, TransferFrame
from repo2ree_protocol.workbench import (
    CancelRunRequest,
    CopyAbortRequest,
    CopyChunkRequest,
    CopyCloseRequest,
    CopyOpenRequest,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
)
from repo2ree_workbench.dispatcher import dispatch_workbench_request
from repo2ree_workbench.service import WorkbenchService
from repo2ree_workbench.transfers import TransferStore


class _Service:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.copied = b""

    def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str]):
        self.calls.append(("exec_action", cmd_json, run_id, env))
        yield DoneFrame()

    def exec_query_stream(self, argv: list[str], timeout: int):
        self.calls.append(("exec_query", argv, timeout))
        yield b"query-result"

    def cancel_run(self, run_id: str) -> None:
        self.calls.append(("cancel_run", run_id))

    def exec_simple(self, argv: list[str], timeout: int) -> None:
        self.calls.append(("exec_simple", argv, timeout))

    def copy_in(self, source_path: str, workbench_path: str) -> None:
        self.calls.append(("copy_in", workbench_path))
        self.copied = Path(source_path).read_bytes()


class _Harness:
    def __init__(self) -> None:
        self.service = _Service()
        self.transfers = TransferStore()
        self.frames: list[Frame] = []
        self.byte_results: list[bytes] = []
        self.received: list[int] = []

    async def dispatch(self, request: Any) -> None:
        async def send(frame: Frame) -> None:
            self.frames.append(frame)

        async def pump(factory: Any) -> None:
            self.frames.extend(factory())

        async def pump_bytes(factory: Any) -> None:
            self.byte_results.extend(factory())

        await dispatch_workbench_request(
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
        await harness.dispatch(ExecActionRequest(cmd_json="{}", run_id="run-1", env={"TRACE_RELAY": "1"}))
        await harness.dispatch(ExecQueryRequest(argv=["archive"], timeout=12))

    asyncio.run(scenario())

    assert [call[0] for call in harness.service.calls] == ["exec_action", "exec_query"]
    assert [frame.type for frame in harness.frames] == ["done"]
    assert harness.byte_results == [b"query-result"]


def test_dispatcher_routes_simple_requests_and_terminal_frames() -> None:
    harness = _Harness()

    async def scenario() -> None:
        await harness.dispatch(CancelRunRequest(run_id="run-1"))
        await harness.dispatch(ExecSimpleRequest(argv=["doctor"], timeout=7))

    asyncio.run(scenario())

    assert [call[0] for call in harness.service.calls] == ["cancel_run", "exec_simple"]
    assert [frame.type for frame in harness.frames] == ["done", "done"]


def test_dispatcher_reassembles_close_and_aborts_copy_transfers() -> None:
    harness = _Harness()

    async def scenario() -> None:
        await harness.dispatch(CopyOpenRequest(workbench_path="/ree/input.bin"))
        transfer = cast(TransferFrame, harness.frames.pop()).transfer_id
        payload = b"transferred"
        await harness.dispatch(
            CopyChunkRequest(transfer_id=transfer, offset=0, data_b64=base64.b64encode(payload).decode())
        )
        await harness.dispatch(CopyCloseRequest(transfer_id=transfer))

        await harness.dispatch(CopyOpenRequest(workbench_path="/ree/aborted.bin"))
        aborted = cast(TransferFrame, harness.frames.pop()).transfer_id
        await harness.dispatch(CopyAbortRequest(transfer_id=aborted))

    asyncio.run(scenario())

    assert harness.service.copied == b"transferred"
    assert harness.received == [len(b"transferred")]
    assert [frame.type for frame in harness.frames] == ["done", "done", "done"]
