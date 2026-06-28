"""Real end-to-end test of a workbench, with no stubs.

This is the highest-fidelity tier: it provisions an actual workbench
container from the built ``repo2ree-workbench:latest`` image and drives the
REE lifecycle through the real ``WorkbenchManager`` — real ``docker run`` /
``docker exec`` transport, the real ``repo2ree-exec`` executor inside the
container, real core handlers operating on a real ``/ree`` volume, the real
NDJSON log relay over stderr, and the real ``ActionResult`` over stdout.

Nothing is mocked or redirected. The cost is that it needs Docker and the
workbench image, so the whole module is skipped (never faked) when either is
absent. Build the image with ``make workbench-image``.

Flow exercised over the real transport:
    provision -> get-ree -> write_file -> read-file round-trip
        -> build_runtime (real script run inside the workbench)
        -> seal_ree -> build-archive -> teardown
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from repo2ree_protocol.command import (
    BuildRuntimeCommand,
    SealReeCommand,
    WriteFileArgs,
    WriteFileCommand,
)
from repo2ree_supervisor import WorkbenchHandle, WorkbenchManager, WorkbenchRegistry

# ================================================
# Constants
# ================================================


WORKBENCH_IMAGE = "repo2ree-workbench:latest"

TEST_RESULTS_DIR = Path(__file__).resolve().parents[3] / "test-artifacts" / "traces" / "supervisor-e2e"


# ================================================
# Skip gate
# ================================================


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "version"], capture_output=True).returncode == 0


def _image_present(image: str) -> bool:
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available() or not _image_present(WORKBENCH_IMAGE),
    reason=f"real workbench e2e needs docker + the {WORKBENCH_IMAGE} image (run: make workbench-image)",
)


# ================================================
# Fixtures
# ================================================


@pytest.fixture
def workbench(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[tuple[WorkbenchManager, WorkbenchHandle]]:
    """Provision a real workbench container; tear it down unconditionally.

    Before teardown, the container's logs are snapshotted into
    ``test-results/supervisor-e2e/<test>/workbench.log`` so a failed run can
    still be inspected after the container is gone.
    """
    registry = WorkbenchRegistry(tmp_path / "registry.json")
    manager = WorkbenchManager(registry=registry, workbench_image=WORKBENCH_IMAGE)
    ree_id = uuid4().hex[:12]
    handle = manager.provision(ree_id, name="e2e-test")
    try:
        yield manager, handle
    finally:
        _dump_workbench_logs(handle.container_name, request.node.name)
        manager.teardown(handle)


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


def test_workbench_lifecycle_e2e(workbench: tuple[WorkbenchManager, WorkbenchHandle]) -> None:
    manager, handle = workbench

    events: list[tuple[str, str, str]] = []

    def log(stream: str, level: str, message: str) -> None:
        events.append((stream, level, message))

    # --- init produced metadata on the real /ree volume ----------------
    metadata = manager.get_ree_metadata(handle)
    assert metadata["reeId"] == handle.ree_id
    assert metadata["status"] == "draft"

    # --- write_file: dispatched over real `docker exec` ----------------
    # The build always runs the reserved, REE-owned build script, so author the
    # recipe there.
    build_script = "ree/build_script.sh"
    result = manager.dispatch_action(
        handle,
        WriteFileCommand(args=WriteFileArgs(path=build_script, content="echo building runtime\n")),
        "write",
        log,
    )
    assert result.status == "succeeded"

    # read it back through the real read-file query — full round-trip
    assert manager.read_file_bytes(handle, build_script) == b"echo building runtime\n"
    workspace = manager.get_workspace(handle)
    assert any(f.get("path") == build_script for f in workspace["files"])

    # --- build_runtime: real script execution inside the workbench -----
    result = manager.dispatch_action(
        handle,
        BuildRuntimeCommand(),
        "build",
        log,
    )
    assert result.status == "succeeded"

    # --- seal_ree: produce the immutable bundle on the volume ----------
    result = manager.dispatch_action(handle, SealReeCommand(), "seal", log)
    assert result.status == "succeeded"
    assert result.outputs["sealHash"].startswith("sha256:")

    # --- build-archive: real sealed zip streamed back over the wire ----
    archive = manager.build_archive(handle)
    with zipfile.ZipFile(BytesIO(archive)) as zf:
        assert zf.namelist()  # a valid, non-empty zip

    # the real NDJSON log relay carried events back from the container
    assert events
