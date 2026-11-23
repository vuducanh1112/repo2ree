from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
import threading
import time
import zipfile
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from repo2ree_protocol.command import (
    AcquireSourceArgs,
    AcquireSourceCommand,
    BuildExperimentEnvironmentCommand,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    SealReeCommand,
    WriteScriptArgs,
    WriteScriptCommand,
)
from repo2ree_protocol.workbench import workbench_hello_adapter
from repo2ree_supervisor import (
    CommandDispatcher,
    ReeLocks,
    ReeRoute,
    WorkbenchConnection,
    WorkbenchConnectionRegistry,
    WsWorkbenchClient,
)
from repo2ree_supervisor.sessions import Session
from repo2ree_supervisor.transfers import TRANSFER_PATH_PREFIX, TransferError, Transfers
from repo2ree_telemetry.relay import build_span_sink
from repo2ree_testbed.artifacts import case_dir, service_dir

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "tools"

TEST_RESULTS_DIR = service_dir("supervisor-e2e")
STORE_ID = "e2e-lab"

_UPLOAD_TOKEN = "e2e-upload"  # noqa: S105
_EXPERIMENT_ENVIRONMENT_ARTIFACT = "runtime.bin"


pytestmark = pytest.mark.skipif(
    not (_TOOLS_BUNDLE / "manifest.json").is_file(),
    reason="real workbench e2e needs the tools bundle (run: just build-e2e-bundles)",
)


TRANSFERS = Transfers()


@pytest.fixture
def connections() -> Iterator[tuple[WorkbenchConnectionRegistry, int]]:
    port = _free_port()
    registry = WorkbenchConnectionRegistry()
    loop = asyncio.new_event_loop()

    async def handler(ws: WebSocket) -> None:
        await ws.accept()

        def send_text(text: str) -> None:
            asyncio.run_coroutine_threadsafe(ws.send_text(text), loop)

        hello = workbench_hello_adapter.validate_json(await ws.receive_text())
        session = Session(hello, registered=True)
        connection = WorkbenchConnection(send_text=send_text, hello=hello, session=session)
        registry.register(hello.workbench_id, connection)
        session.connect()
        try:
            while True:
                connection.on_message(await ws.receive_text())
        except WebSocketDisconnect:
            pass
        finally:
            connection.close()
            registry.unregister(hello.workbench_id, connection)

    async def offered(request: Request) -> Response:
        try:
            return FileResponse(TRANSFERS.serve(request.path_params["token"]))
        except TransferError:
            return Response(status_code=404)

    async def transfer(request: Request) -> Response:
        length = request.headers.get("content-length", "")
        try:
            await TRANSFERS.receive(
                request.path_params["token"], request.stream(), int(length) if length.isdigit() else None
            )
        except TransferError:
            return Response(status_code=404)
        return Response(status_code=204)

    app = Starlette(
        routes=[
            WebSocketRoute("/workbench/connect", handler),
            Route(TRANSFER_PATH_PREFIX + "{token}", transfer, methods=["PUT"]),
            Route(TRANSFER_PATH_PREFIX + "{token}", offered, methods=["GET"]),
        ]
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    task_holder: list[asyncio.Task[None]] = []

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        task = loop.create_task(server.serve())
        task_holder.append(task)
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)
        loop.close()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    try:
        yield registry, port
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture
def workbench(
    tmp_path: Path, connections: tuple[WorkbenchConnectionRegistry, int], request: pytest.FixtureRequest
) -> Iterator[tuple[CommandDispatcher, ReeRoute]]:
    registry, port = connections
    logs = case_dir(request.node.nodeid) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    command = [
        *(sys.executable, "-m", "repo2ree_workbench", "--name", "e2e-workbench"),
        *("--store", f"{STORE_ID}={tmp_path / 'store'}"),
        *("--connect", f"ws://127.0.0.1:{port}/workbench/connect", "--tools-bundle", str(_TOOLS_BUNDLE)),
    ]
    with (logs / "workbench.log").open("w") as log:
        process = subprocess.Popen(
            command,
            env={**os.environ, "WORKBENCH_STATE_DIR": str(tmp_path / "state")},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_connected(registry, "e2e-workbench", process)
            dispatcher = CommandDispatcher(
                WsWorkbenchClient(registry, TRANSFERS), ReeLocks(), build_span_sink(None, console_fallback=True)
            )
            handle = ReeRoute(ree_id=uuid4().hex[:12], workbench_id="e2e-workbench", store_id=STORE_ID)
            dispatcher.init_ree(handle, "e2e-test")
            try:
                yield dispatcher, handle
            finally:
                dispatcher.delete_ree(handle)
        finally:
            process.terminate()
            process.wait(timeout=10)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_connected(
    registry: WorkbenchConnectionRegistry, workbench_id: str, process: subprocess.Popen[bytes], timeout: float = 30.0
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("the store's workbench exited before it connected")
        if registry.store_workbench(STORE_ID) == workbench_id:
            return
        time.sleep(0.05)
    raise RuntimeError(f"workbench did not dial in within {timeout}s")


def test_workbench_lifecycle_e2e(workbench: tuple[CommandDispatcher, ReeRoute], tmp_path: Path) -> None:
    dispatcher, handle = workbench

    events: list[tuple[str, str, str]] = []

    def log(stream: str, level: str, message: str) -> None:
        events.append((stream, level, message))

    manifest = dispatcher.get_ree_manifest(handle)
    assert manifest.seal is None
    assert manifest.subject.definition.name
    document = dispatcher.get_ree_document(handle)
    assert document.status == "draft"

    source_zip = tmp_path / "source.zip"
    with zipfile.ZipFile(source_zip, "w") as source_archive:
        source_archive.writestr("main.py", "print('hello from upstream')\n")
    dispatcher.copy_to_workbench(handle, str(source_zip), f"upload-staging/{_UPLOAD_TOKEN}.bin")
    result = dispatcher.dispatch_action(
        handle,
        AcquireSourceCommand(
            args=AcquireSourceArgs(mode="upload", upload_token=_UPLOAD_TOKEN, archive_name="source.zip")
        ),
        "source",
        log,
    )
    assert result.status == "succeeded", result.failure
    assert dispatcher.read_ree_file_bytes(handle, "workspace/main.py") == b"print('hello from upstream')\n"

    build_experiment_environment_script = "ree-scripts/build_experiment_environment.sh"
    build_body = (
        f"echo building experiment environment\nprintf 'runtime-bytes\\n' > {_EXPERIMENT_ENVIRONMENT_ARTIFACT}\n"
    )
    result = dispatcher.dispatch_action(
        handle,
        WriteScriptCommand(args=WriteScriptArgs(path=build_experiment_environment_script, content=build_body)),
        "write",
        log,
    )
    assert result.status == "succeeded"

    assert (
        dispatcher.read_ree_file_bytes(handle, f"workspace/{build_experiment_environment_script}")
        == build_body.encode()
    )
    workspace = dispatcher.get_ree_document(handle)
    assert any(f.path == build_experiment_environment_script for f in workspace.workspace_files)

    result = dispatcher.dispatch_action(
        handle,
        PatchReeDefinitionCommand(
            args=PatchReeDefinitionArgs(
                patch={"experiment_environment": {"artifact_path": _EXPERIMENT_ENVIRONMENT_ARTIFACT}},
                expected_version="",
            )
        ),
        "patch-definition",
        log,
    )
    assert result.status == "succeeded", result.failure

    result = dispatcher.dispatch_action(
        handle,
        BuildExperimentEnvironmentCommand(),
        "build_experiment_environment",
        log,
    )
    assert result.status == "succeeded", result.failure

    result = dispatcher.dispatch_action(handle, SealReeCommand(), "seal", log)
    assert result.status == "succeeded", result.failure
    assert result.outputs["ree_digest"].startswith("sha256:")

    archive = dispatcher.build_archive(handle)
    try:
        with zipfile.ZipFile(archive.path) as zf:
            assert zf.namelist()
    finally:
        archive.path.unlink()

    assert events
