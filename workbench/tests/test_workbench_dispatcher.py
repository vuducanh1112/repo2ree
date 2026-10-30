from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar, cast

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import DoneFrame, Frame
from repo2ree_protocol.workbench import (
    AssignAllocationRequest,
    CancelRunRequest,
    ExecActionRequest,
    ExecQueryRequest,
    ExecSimpleRequest,
    ExecUploadRequest,
    FetchFileRequest,
)
from repo2ree_workbench.dispatcher import dispatch_workbench_request
from repo2ree_workbench.service import WorkbenchService


class _Service:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.copied = b""

    def assign(self, allocation: AllocationRequest) -> None:
        self.calls.append(("assign", allocation.allocation_id))

    def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str], context=None):
        self.calls.append(("exec_action", cmd_json, run_id, env))
        yield DoneFrame()

    def exec_query_stream(self, argv: list[str], timeout: int):
        self.calls.append(("exec_query", argv, timeout))
        yield b"query-result"

    def exec_query_to_file(self, argv: list[str], target: Path, timeout: int) -> None:
        self.calls.append(("exec_query_to_file", argv, timeout))
        target.write_bytes(b"archive-bytes")

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
        self.frames: list[Frame] = []
        self.byte_results: list[bytes] = []
        self.received: list[int] = []

    async def dispatch(self, request: Any, api_ws_url: str = "") -> None:
        async def send(frame: Frame) -> None:
            self.frames.append(frame)

        async def pump(factory: Any) -> None:
            self.frames.extend(factory())

        async def pump_bytes(factory: Any) -> None:
            self.byte_results.extend(factory())

        await dispatch_workbench_request(
            request,
            cast(WorkbenchService, self.service),
            send=send,
            pump=pump,
            pump_bytes=pump_bytes,
            record_received=self.received.append,
            api_ws_url=api_ws_url,
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


def test_dispatcher_routes_assignment_before_any_execution() -> None:
    # Assignment is an ordinary request on the execution connection: it reaches
    # the service and is acknowledged like any other terminal operation.
    harness = _Harness()
    allocation = AllocationRequest(
        allocation_id="alloc-1",
        ree_id="ree-1",
        location_id="lab-1",
        image="docker.io/library/docker:29-dind",
    )

    asyncio.run(harness.dispatch(AssignAllocationRequest(allocation=allocation)))

    assert harness.service.calls == [("assign", "alloc-1")]
    assert [frame.type for frame in harness.frames] == ["done"]


class _Receiver(BaseHTTPRequestHandler):
    """A control plane's transfer route: keeps each PUT body by path, serves each offered file once."""

    received: ClassVar[dict[str, bytes]] = {}
    offered: ClassVar[dict[str, bytes]] = {}

    def do_GET(self) -> None:
        content = self.offered.pop(self.path, None)
        if content is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_PUT(self) -> None:
        length = int(self.headers["Content-Length"])
        self.received[self.path] = self.rfile.read(length)
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the http.server signature
        return


def test_an_upload_request_sends_the_query_output_to_the_address_the_workbench_dialed(tmp_path: Path) -> None:
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    harness = _Harness()
    try:
        asyncio.run(
            harness.dispatch(
                ExecUploadRequest(argv=["build-archive"], transfer_path="/workbench/transfers/t1", timeout=30),
                api_ws_url=f"ws://127.0.0.1:{server.server_port}/workbench/connect",
            )
        )
    finally:
        server.shutdown()

    assert harness.service.calls == [("exec_query_to_file", ["build-archive"], 30)]
    assert _Receiver.received == {"/workbench/transfers/t1": b"archive-bytes"}
    assert [frame.type for frame in harness.frames] == ["done"]


def test_a_fetch_request_lands_the_offered_file_in_the_bench_and_counts_its_bytes() -> None:
    server = HTTPServer(("127.0.0.1", 0), _Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Receiver.offered["/workbench/transfers/t2"] = b"source-archive"
    harness = _Harness()
    try:
        asyncio.run(
            harness.dispatch(
                FetchFileRequest(transfer_path="/workbench/transfers/t2", workbench_path="/ree/upload.tar.gz"),
                api_ws_url=f"ws://127.0.0.1:{server.server_port}/workbench/connect",
            )
        )
    finally:
        server.shutdown()

    assert harness.service.calls == [("copy_in", "/ree/upload.tar.gz")]
    assert harness.service.copied == b"source-archive"
    assert harness.received == [len(b"source-archive")]
    assert [frame.type for frame in harness.frames] == ["done"]
