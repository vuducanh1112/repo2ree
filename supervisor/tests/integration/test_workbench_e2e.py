"""Real end-to-end test of a workbench, with no stubs.

This is the highest-fidelity tier: it provisions an actual workbench container
from the pinned upstream ``docker:dind`` bench — with the executor/tools
bundles injected by the agent, exactly like production — and drives the REE
lifecycle through the real ``WorkbenchManager`` over the production transport:
the real ``repo2ree_agent`` dials an in-test control-plane WebSocket, holds it
open, and ``WsAgentClient`` drives it. Real ``docker run`` / ``docker exec``
inside the agent, the real injected ``repo2ree-exec`` executor inside the
container, real core handlers on a real ``/ree`` volume, the real
``AgentFrame`` stream over the socket, and the real ``ActionResult``.

Nothing is mocked or redirected. The cost is that it needs Docker and the
bundles, so the whole module is skipped (never faked) when either is absent.
Build the bundles with ``make e2e-bundles``.

Flow exercised over the real agent:
    provision -> get-ree -> acquire_source (staged upload, no network)
        -> write_file -> read-ree-file round-trip -> patch_ree_definition
        -> build_runtime (real script run inside the workbench)
        -> seal_ree -> build-archive -> teardown

The order is the domain's, not a convenience: each step here is a precondition
of the next, and the handlers enforce that. A build with no acquired source is
refused because its receipt would have no snapshot to bind to, and a seal is
refused if any receipt has gone stale under it.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import zipfile
from collections.abc import Iterator
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from websockets.asyncio.server import ServerConnection, serve

from repo2ree_agent.control_link import run_agent
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
from repo2ree_supervisor import (
    AgentConnection,
    AgentConnectionRegistry,
    WorkbenchHandle,
    WorkbenchManager,
    WorkbenchRegistry,
    WorkbenchUnavailableError,
    WsAgentClient,
)

# ================================================
# Constants
# ================================================


# The production bench: upstream dind pinned by digest (keep in sync with the
# catalog default in api/src/repo2ree_api/settings.py). The in-test agent
# injects the executor/tools bundles, so this tier drives the exact
# provisioning path production uses. First run pulls the image.
WORKBENCH_IMAGE = (
    "docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515"
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXEC_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "exec"
_TOOLS_BUNDLE = _REPO_ROOT / "dist" / "bundles" / "tools"
# Must be set before the agent's DockerRuntime is constructed (fixture below).
os.environ.setdefault("REPO2REE_EXEC_BUNDLE", str(_EXEC_BUNDLE))
os.environ.setdefault("REPO2REE_TOOLS_BUNDLE", str(_TOOLS_BUNDLE))

TEST_RESULTS_DIR = Path(__file__).resolve().parents[3] / "test-artifacts" / "traces" / "supervisor-e2e"

# The staging slot the upload acquisition reads from; the API mints these per
# request, but the name only has to agree with the file we place in the bench.
_UPLOAD_TOKEN = "e2e-upload"  # noqa: S105 — a staging filename, not a credential
# Where the build script leaves its runtime, declared on the definition so the
# build receipt can bind that path to the digest found there.
_RUNTIME_ARTIFACT = "runtime.bin"


# ================================================
# Skip gate
# ================================================


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "version"], capture_output=True).returncode == 0


def _bundles_present() -> bool:
    return (_EXEC_BUNDLE / "manifest.json").is_file() and (_TOOLS_BUNDLE / "manifest.json").is_file()


pytestmark = pytest.mark.skipif(
    not _docker_available() or not _bundles_present(),
    reason="real workbench e2e needs docker + the executor/tools bundles (run: make e2e-bundles)",
)


# ================================================
# Fixtures
# ================================================


@pytest.fixture
def agent_registry() -> Iterator[AgentConnectionRegistry]:
    """Run the real outbound agent dialing an in-test control-plane socket.

    Mirrors production: the agent dials ``/agent/connect``, holds one WebSocket,
    and the manager drives it through ``WsAgentClient``. A raw ``websockets``
    server stands in for the API's route (same bridge: ``send_text`` schedules on
    the loop, inbound frames feed ``on_message``), so the test needs no HTTP app.
    The event loop runs in a background thread while the synchronous manager
    blocks on it from the test thread.
    """
    port = _free_port()
    registry = AgentConnectionRegistry()
    loop = asyncio.new_event_loop()

    async def handler(ws: ServerConnection) -> None:
        def send_text(text: str) -> None:
            asyncio.run_coroutine_threadsafe(ws.send(text), loop)

        hello = json.loads(await ws.recv())
        agent_id = hello.get("agent_id", "default")
        connection = AgentConnection(send_text=send_text)
        registry.register(agent_id, connection)
        try:
            async for message in ws:
                connection.on_message(message if isinstance(message, str) else message.decode())
        finally:
            connection.close()
            registry.unregister(agent_id, connection)

    async def serve_and_dial() -> None:
        async with serve(handler, "127.0.0.1", port):
            await run_agent(f"ws://127.0.0.1:{port}/agent/connect", "dind", "e2e-agent")

    task_holder: list[asyncio.Task[None]] = []

    def run_loop() -> None:
        asyncio.set_event_loop(loop)
        task = loop.create_task(serve_and_dial())
        task_holder.append(task)
        with suppress(asyncio.CancelledError):
            loop.run_until_complete(task)
        loop.close()

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    _wait_until_agent_connected(registry)
    try:
        yield registry
    finally:
        # Cancel the server/agent task so the loop drains cleanly (closes the
        # WebSocket, stops the server) instead of being killed mid-flight.
        loop.call_soon_threadsafe(task_holder[0].cancel)
        thread.join(timeout=10)


@pytest.fixture
def workbench(
    tmp_path: Path, agent_registry: AgentConnectionRegistry, request: pytest.FixtureRequest
) -> Iterator[tuple[WorkbenchManager, WorkbenchHandle]]:
    """Provision a real workbench container; tear it down unconditionally.

    Before teardown, the container's logs are snapshotted into
    ``test-results/supervisor-e2e/<test>/workbench.log`` so a failed run can
    still be inspected after the container is gone.
    """
    registry = WorkbenchRegistry(tmp_path / "registry.json")
    manager = WorkbenchManager(registry=registry, workbench_image=WORKBENCH_IMAGE, agent=WsAgentClient(agent_registry))
    ree_id = uuid4().hex[:12]
    handle = manager.provision(ree_id, name="e2e-test")
    try:
        yield manager, handle
    finally:
        _dump_workbench_logs(handle.container_name, request.node.name)
        manager.teardown(handle)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_agent_connected(registry: AgentConnectionRegistry, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            registry.pick()
            return
        except WorkbenchUnavailableError:
            time.sleep(0.05)
    raise RuntimeError(f"agent did not dial in within {timeout}s")


def _dump_workbench_logs(container_name: str, test_name: str) -> None:
    """Snapshot the workbench's logs before it is torn down.

    ``workbench.log`` is the container's entrypoint output; ``dockerd.log`` is
    the in-container Docker daemon's log (the entrypoint redirects it to
    ``/var/log/dockerd.log``), which is where runtime-build failures surface.
    """
    out_dir = TEST_RESULTS_DIR / test_name
    out_dir.mkdir(parents=True, exist_ok=True)

    entrypoint = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
    (out_dir / "workbench.log").write_text(entrypoint.stdout + entrypoint.stderr)

    dockerd = subprocess.run(
        ["docker", "exec", container_name, "cat", "/var/log/dockerd.log"],
        capture_output=True,
        text=True,
    )
    (out_dir / "dockerd.log").write_text(dockerd.stdout + dockerd.stderr)


# ================================================
# E2E flow
# ================================================


def test_workbench_lifecycle_e2e(workbench: tuple[WorkbenchManager, WorkbenchHandle], tmp_path: Path) -> None:
    manager, handle = workbench

    events: list[tuple[str, str, str]] = []

    def log(stream: str, level: str, message: str) -> None:
        events.append((stream, level, message))

    # --- init produced metadata on the real /ree volume ----------------
    # The manifest is the portable aggregate and nothing else: no handle (that
    # is the control plane's) and no status (that is derived from the seal).
    manifest = manager.get_ree_manifest(handle)
    assert sorted(manifest) == ["subject"]
    assert manifest["subject"]["definition"]["name"]
    # Both of those reach the API through the composed document, where the
    # manager stamps the handle it alone knows and core derives the status.
    document = manager.get_ree_document(handle)
    assert document["ree_id"] == handle.ree_id
    assert document["status"] == "draft"

    # --- acquire_source: the REE gets something to build from ----------
    # Building requires acquired source: a runtime built from nothing attests to
    # nothing, so the receipt chain is rooted at a snapshot digest and the
    # handler refuses without one. The upload basis is the one that needs no
    # network — stage an archive where the handler looks for it and acquire from
    # there, which is exactly what the API's upload-init/upload/complete
    # sequence does, over the same real `docker cp` transport.
    source_zip = tmp_path / "source.zip"
    with zipfile.ZipFile(source_zip, "w") as source_archive:
        source_archive.writestr("main.py", "print('hello from upstream')\n")
    manager.copy_to_workbench(handle, str(source_zip), f"/ree/upload-staging/{_UPLOAD_TOKEN}.bin")
    result = manager.dispatch_action(
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
    assert manager.read_ree_file_bytes(handle, "workspace/main.py") == b"print('hello from upstream')\n"

    # --- write_file: dispatched over real `docker exec` ----------------
    # The build always runs the reserved, REE-owned build script, so author the
    # recipe there. It has to *produce* the declared runtime: the handler digests
    # the artifact for the receipt and fails the run if the script exits clean
    # without leaving one behind.
    build_script = "ree-scripts/build_script.sh"
    build_body = f"echo building runtime\nprintf 'runtime-bytes\\n' > {_RUNTIME_ARTIFACT}\n"
    result = manager.dispatch_action(
        handle,
        WriteFileCommand(args=WriteFileArgs(path=build_script, content=build_body)),
        "write",
        log,
    )
    assert result.status == "succeeded"

    # read it back through the real read-ree-file query — full round-trip
    assert manager.read_ree_file_bytes(handle, f"workspace/{build_script}") == build_body.encode()
    workspace = manager.get_ree_document(handle)
    assert any(f.get("path") == build_script for f in workspace["workspace_files"])

    # --- declare where the build leaves its runtime --------------------
    # Nothing infers this: the author says which artifact is the runtime, and
    # the build receipt binds that path to the digest it found there.
    result = manager.dispatch_action(
        handle,
        PatchReeDefinitionCommand(
            args=PatchReeDefinitionArgs(patch={"runtime": {"runtime_path": _RUNTIME_ARTIFACT}}, expected_version="")
        ),
        "patch-definition",
        log,
    )
    assert result.status == "succeeded", result.failure

    # --- build_runtime: real script execution inside the workbench -----
    result = manager.dispatch_action(
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
    result = manager.dispatch_action(handle, SealReeCommand(), "seal", log)
    assert result.status == "succeeded", result.failure
    assert result.outputs["ree_digest"].startswith("sha256:")

    # --- build-archive: real sealed zip streamed back over the wire ----
    archive = manager.build_archive(handle)
    with zipfile.ZipFile(BytesIO(archive)) as zf:
        assert zf.namelist()  # a valid, non-empty zip

    # the real NDJSON log relay carried events back from the container
    assert events
