"""Real end-to-end test of a store's workbench, with no stubs.

This is the highest-fidelity tier below the API: a real ``repo2ree_workbench``
process serves a store on this host, dials an in-test control-plane WebSocket,
holds it open, and the ``CommandDispatcher`` drives one REE in it through
``WsWorkbenchClient`` over the production transport. Real ``repo2ree-exec``
executors, real core handlers on the REE's real directory in the store, the
real ``Frame`` stream over the socket, files offered and uploaded over real
HTTP beside it, and the real ``ActionResult``.

Nothing is mocked or redirected. The cost is that it needs the tools bundle
(sealing stores payloads with git-lfs), so the whole module is skipped (never
faked) when it is absent. Build it with ``just build-e2e-bundles``.

Flow exercised over the real workbench:
    init-ree -> get-ree -> acquire_source (staged upload, no network)
        -> write_file -> read-ree-file round-trip -> patch_ree_definition
        -> build_runtime (real script run by the workbench)
        -> seal_ree -> build-archive -> delete

The order is the domain's, not a convenience: each step here is a precondition
of the next, and the handlers enforce that. A build with no acquired source is
refused because its receipt would have no snapshot to bind to, and a seal is
refused if any receipt has gone stale under it.
"""

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
    BuildRuntimeCommand,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    SealReeCommand,
    WriteFileArgs,
    WriteFileCommand,
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
from repo2ree_supervisor.transfers import TRANSFER_PATH_PREFIX, TransferError, Transfers
from repo2ree_telemetry.relay import build_span_sink
from repo2ree_testbed.artifacts import case_dir, service_dir

# ================================================
# Constants
# ================================================


_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "tools"

TEST_RESULTS_DIR = service_dir("supervisor-e2e")
STORE_ID = "e2e-lab"

# The staging slot the upload acquisition reads from; the API mints these per
# request, but the name only has to agree with the file we place in the REE.
_UPLOAD_TOKEN = "e2e-upload"  # noqa: S105 — a staging filename, not a credential
# Where the build script leaves its runtime, declared on the definition so the
# build receipt can bind that path to the digest found there.
_RUNTIME_ARTIFACT = "runtime.bin"


# ================================================
# Skip gate
# ================================================


pytestmark = pytest.mark.skipif(
    not (_TOOLS_BUNDLE / "manifest.json").is_file(),
    reason="real workbench e2e needs the tools bundle (run: just build-e2e-bundles)",
)


# Files the workbench uploads beside its control socket (an REE archive) or fetches from beside
# it, shared by the in-test control plane's transfer routes and the dispatcher's client.
TRANSFERS = Transfers()


# ================================================
# Fixtures
# ================================================


@pytest.fixture
def connections() -> Iterator[tuple[WorkbenchConnectionRegistry, int]]:
    """An in-test control plane a store's workbench dials; its registry and port.

    Mirrors production: the workbench dials ``/workbench/connect``, holds one WebSocket,
    and the dispatcher drives it through ``WsWorkbenchClient``. A small Starlette app
    under uvicorn stands in for the API's routes (same bridge: ``send_text``
    schedules on the loop, inbound frames feed ``on_message``), including the
    transfer routes a workbench uploads an archive to and fetches a file from
    (``TRANSFERS``). The event loop runs in a background thread while the
    synchronous dispatcher blocks on it from the test thread.
    """
    port = _free_port()
    registry = WorkbenchConnectionRegistry()
    loop = asyncio.new_event_loop()

    async def handler(ws: WebSocket) -> None:
        await ws.accept()

        def send_text(text: str) -> None:
            asyncio.run_coroutine_threadsafe(ws.send_text(text), loop)

        hello = workbench_hello_adapter.validate_json(await ws.receive_text())
        connection = WorkbenchConnection(send_text=send_text, hello=hello)
        registry.register(hello.workbench_id, connection)
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
    """A store's workbench serving one new REE; the REE is deleted and the workbench stopped afterwards.

    The workbench's output lands in ``test-results/supervisor-e2e/<test>/logs/workbench.log``
    so a failed run can still be inspected.
    """
    registry, port = connections
    logs = case_dir(request.node.nodeid) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    command = [
        *(sys.executable, "-m", "repo2ree_workbench", "--name", "e2e-workbench"),
        *("--store", f"{STORE_ID}={tmp_path / 'store'}", "--backend", "host"),
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
            # With a span sink the dispatcher asks the executor to relay its spans back over stderr;
            # without one it never sets TRACE_RELAY, and the half of the flow the workbench runs
            # would be missing from the record entirely.
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


# ================================================
# E2E flow
# ================================================


def test_workbench_lifecycle_e2e(workbench: tuple[CommandDispatcher, ReeRoute], tmp_path: Path) -> None:
    dispatcher, handle = workbench

    events: list[tuple[str, str, str]] = []

    def log(stream: str, level: str, message: str) -> None:
        events.append((stream, level, message))

    # --- init produced metadata in the REE's directory of the store ---
    manifest = dispatcher.get_ree_manifest(handle)
    assert manifest.seal is None
    assert manifest.subject.definition.name
    document = dispatcher.get_ree_document(handle)
    assert document.status == "draft"

    # --- acquire_source: the REE gets something to build from ----------
    # Building requires acquired source: a runtime built from nothing attests to
    # nothing, so the receipt chain is rooted at a snapshot digest and the
    # handler refuses without one. The upload basis is the one that needs no
    # network — stage an archive where the handler looks for it and acquire from
    # there, which is exactly what the API's upload-init/upload/complete
    # sequence does, over the same real chunked transfer.
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
    # Acquisition materializes the workspace from upstream + overlay, so the
    # uploaded tree is what a build will actually see.
    assert dispatcher.read_ree_file_bytes(handle, "workspace/main.py") == b"print('hello from upstream')\n"

    # --- write_file: dispatched over the workbench's socket -----------
    # The build always runs the reserved, REE-owned build script, so author the
    # recipe there. It has to *produce* the declared runtime: the handler digests
    # the artifact for the receipt and fails the run if the script exits clean
    # without leaving one behind.
    build_script = "ree-scripts/build_script.sh"
    build_body = f"echo building runtime\nprintf 'runtime-bytes\\n' > {_RUNTIME_ARTIFACT}\n"
    result = dispatcher.dispatch_action(
        handle,
        WriteFileCommand(args=WriteFileArgs(path=build_script, content=build_body)),
        "write",
        log,
    )
    assert result.status == "succeeded"

    # read it back through the real read-ree-file query — full round-trip
    assert dispatcher.read_ree_file_bytes(handle, f"workspace/{build_script}") == build_body.encode()
    workspace = dispatcher.get_ree_document(handle)
    assert any(f.path == build_script for f in workspace.workspace_files)

    # --- declare where the build leaves its runtime --------------------
    # Nothing infers this: the author says which artifact is the runtime, and
    # the build receipt binds that path to the digest it found there. It rides
    # on the build recipe rather than beside it — a script and what it produces
    # are one declaration, so the patch carries only the destination and the
    # handler rehydrates the script's identity from the authored file.
    result = dispatcher.dispatch_action(
        handle,
        PatchReeDefinitionCommand(
            args=PatchReeDefinitionArgs(
                patch={"build_runtime": {"runtime_path": _RUNTIME_ARTIFACT}}, expected_version=""
            )
        ),
        "patch-definition",
        log,
    )
    assert result.status == "succeeded", result.failure

    # --- build_runtime: real script execution inside the workbench -----
    result = dispatcher.dispatch_action(
        handle,
        BuildRuntimeCommand(),
        "build",
        log,
    )
    assert result.status == "succeeded", result.failure

    # --- seal_ree: produce the immutable bundle on the volume ----------
    # Sealing audits the REE first and refuses stale evidence, so reaching a
    # digest here also proves the receipts the steps above filed still describe
    # what the volume holds.
    result = dispatcher.dispatch_action(handle, SealReeCommand(), "seal", log)
    assert result.status == "succeeded", result.failure
    assert result.outputs["ree_digest"].startswith("sha256:")

    # --- build-archive: a real sealed zip, uploaded beside the control socket ----
    archive = dispatcher.build_archive(handle)
    try:
        with zipfile.ZipFile(archive.path) as zf:
            assert zf.namelist()  # a valid, non-empty zip
    finally:
        archive.path.unlink()

    # the real NDJSON log relay carried events back from the container
    assert events
