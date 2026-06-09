"""Host-side workbench lifecycle and command dispatch.

Each REE has exactly one always-on workbench container with its volume
mounted at /ree. The manager provisions new workbenches, dispatches
typed Commands via ``docker exec``, and issues cheap queries/mutations
the same way.

Streaming: dispatch_action reads the container's stderr line-by-line
(NDJSON log events) so callers receive log events in real time. The
ActionResult is read from stdout once stderr is exhausted.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from repo2ree_protocol.command import Command, SealReeArgs, SealReeCommand
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_supervisor.registry import WorkbenchEntry, WorkbenchRegistry

logger = logging.getLogger(__name__)

# ================================================
# Constants
# ================================================


# Exit codes from `docker exec` that mean the container is gone / stopping.
# 137 = killed by SIGKILL (container OOM-killed or being removed)
# 126 = OCI runtime exec failed (container shutting down, broken init pipe)
_CONTAINER_GONE_EXIT_CODES = frozenset({126, 137})


# ================================================
# Utility Classes
# ================================================


class WorkbenchUnavailableError(RuntimeError):
    """Raised when a docker exec fails because the container is gone or stopping."""


@dataclass(frozen=True)
class WorkbenchHandle:
    ree_id: str
    container_name: str
    volume_name: str

    @classmethod
    def from_entry(cls, entry: WorkbenchEntry) -> WorkbenchHandle:
        return cls(
            ree_id=entry.ree_id,
            container_name=entry.container_name,
            volume_name=entry.volume_name,
        )


# ================================================
# Manager
# ================================================


class WorkbenchManager:
    def __init__(
        self,
        registry: WorkbenchRegistry,
        workbench_image: str,
    ):
        self._registry = registry
        self._image = workbench_image
        self._ree_locks: dict[str, threading.Lock] = {}
        self._ree_locks_lock = threading.Lock()

    def _ree_lock(self, ree_id: str) -> threading.Lock:
        with self._ree_locks_lock:
            if ree_id not in self._ree_locks:
                self._ree_locks[ree_id] = threading.Lock()
            return self._ree_locks[ree_id]

    # ------------------------------------------------
    # Lifecycle
    # ------------------------------------------------

    def provision(self, ree_id: str, name: str) -> WorkbenchHandle:
        """Create volume + container, initialise the REE, register handle."""
        volume_name = f"repo2ree-ree-{ree_id}"
        dind_volume_name = _dind_volume_name(ree_id)
        container_name = f"repo2ree-wb-{ree_id}"

        _docker("volume", "create", volume_name)
        _docker("volume", "create", dind_volume_name)

        # No host docker.sock mount: the workbench runs its own in-container
        # daemon (docker-in-docker) for full per-REE isolation. /var/lib/docker
        # is volume-backed so the nested daemon uses overlay2, not vfs.
        _docker(
            "run",
            "-d",
            "--privileged",
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            "-e",
            "DOCKER_DRIVER=overlay2",
            "-v",
            f"{volume_name}:/ree",
            "-v",
            f"{dind_volume_name}:/var/lib/docker",
            self._image,
            "sleep",
            "infinity",
        )

        _docker_exec(
            container_name,
            "repo2ree-exec",
            "init-ree",
            "--ree-id",
            ree_id,
            "--name",
            name,
        )

        entry = WorkbenchEntry(
            ree_id=ree_id,
            container_name=container_name,
            volume_name=volume_name,
        )
        self._registry.register(entry)
        return WorkbenchHandle.from_entry(entry)

    def reprovision(self, ree_id: str) -> WorkbenchHandle:
        """Replace the container with a fresh one from the current image, keeping the volume."""
        entry = self._registry.lookup(ree_id)
        if entry is None:
            raise KeyError(f"no workbench registered for {ree_id}")
        _docker_silent("rm", "-f", entry.container_name)
        _docker(
            "run",
            "-d",
            "--privileged",
            "--name",
            entry.container_name,
            "--restart",
            "unless-stopped",
            "-e",
            "DOCKER_DRIVER=overlay2",
            "-v",
            f"{entry.volume_name}:/ree",
            "-v",
            f"{_dind_volume_name(entry.ree_id)}:/var/lib/docker",
            self._image,
            "sleep",
            "infinity",
        )
        return WorkbenchHandle.from_entry(entry)

    def teardown(self, handle: WorkbenchHandle) -> None:
        """Stop + remove the container and its volumes, unregister."""
        _docker_silent("rm", "-f", handle.container_name)
        _docker_silent("volume", "rm", handle.volume_name)
        _docker_silent("volume", "rm", _dind_volume_name(handle.ree_id))
        self._registry.unregister(handle.ree_id)

    def is_registered(self, ree_id: str) -> bool:
        """True if a workbench is registered for ree_id (regardless of run state)."""
        return self._registry.lookup(ree_id) is not None

    def lookup(self, ree_id: str) -> WorkbenchHandle | None:
        """Return the handle for ree_id, or None if not registered or not running."""
        entry = self._registry.lookup(ree_id)
        if entry is None:
            return None
        handle = WorkbenchHandle.from_entry(entry)
        if not self._is_running(handle.container_name):
            logger.warning(
                "workbench container %s not running for %s — returning None",
                handle.container_name,
                ree_id,
            )
            return None
        return handle

    def _is_running(self, container_name: str) -> bool:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    # ------------------------------------------------
    # Action dispatch
    # ------------------------------------------------

    def dispatch_action(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
    ) -> ActionResult:
        """Run a typed Command inside the workbench; stream logs to log."""
        with self._ree_lock(handle.ree_id):
            return self._dispatch_action_locked(handle, cmd, run_id, log)

    def _dispatch_action_locked(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
    ) -> ActionResult:
        cmd_json = cmd.model_dump_json()

        proc = subprocess.Popen(
            [
                "docker",
                "exec",
                "-i",
                handle.container_name,
                "repo2ree-exec",
                "execute",
                "--action",
                "-",
                "--run-id",
                run_id,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            raise RuntimeError("Popen pipes unavailable — stdin/stdout/stderr not opened")

        proc.stdin.write(cmd_json)
        proc.stdin.close()

        # Stream stderr log events live.
        for raw_line in proc.stderr:
            line = raw_line.rstrip()
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "log":
                    log(event["stream"], event["level"], event["message"])
            except json.JSONDecodeError:
                log("system", "info", line)

        stdout = proc.stdout.read().strip()
        proc.wait()

        if proc.returncode in _CONTAINER_GONE_EXIT_CODES:
            raise WorkbenchUnavailableError(f"docker exec exited {proc.returncode} — container gone or stopping")

        if stdout:
            with suppress(Exception):
                return ActionResult.model_validate_json(stdout)

        return ActionResult(status="failed", exit_code=proc.returncode or 1)

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: WorkbenchHandle, *argv: str) -> bytes:
        """Run a read-only CLI subcommand and return its stdout bytes."""
        result = subprocess.run(
            ["docker", "exec", handle.container_name, "repo2ree-exec", *argv],
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            stdout = result.stdout.decode(errors="replace").strip()
            detail = stderr or stdout or "(no output on stdout/stderr)"
            if result.returncode in _CONTAINER_GONE_EXIT_CODES or "No such container" in detail:
                raise WorkbenchUnavailableError(f"query {argv!r} failed (exit {result.returncode}): {detail}")
            raise RuntimeError(f"query {argv!r} failed (exit {result.returncode}): {detail}")
        return result.stdout

    def get_ree_metadata(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-ree")
        return json.loads(raw)

    def get_workspace(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-workspace")
        return json.loads(raw)

    def read_file_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-file", "--path", path)

    def read_artifact_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-artifact", "--path", path)

    def seal(
        self,
        handle: WorkbenchHandle,
        *,
        source_included: bool,
        runtime_included: bool,
    ) -> dict[str, Any]:
        cmd = SealReeCommand(
            args=SealReeArgs(
                source_included=source_included,
                runtime_included=runtime_included,
            )
        )
        with self._ree_lock(handle.ree_id):
            result = self._dispatch_action_locked(handle, cmd, "seal", lambda *_: None)
        if result.status != "succeeded":
            raise RuntimeError(f"seal_ree {result.status}")
        return self.get_workspace(handle)

    def build_archive(self, handle: WorkbenchHandle) -> bytes:
        with self._ree_lock(handle.ree_id):
            return self.dispatch_query(handle, "build-archive")

    def list_all_metadata(self) -> list[dict[str, Any]]:
        """Return metadata for every registered workbench, skipping unreachable ones."""
        results = []
        for entry in self._registry.list_all():
            handle = WorkbenchHandle.from_entry(entry)
            if not self._is_running(handle.container_name):
                continue
            with suppress(Exception):
                results.append(self.get_ree_metadata(handle))
        results.sort(key=lambda m: m.get("updatedAt", ""), reverse=True)
        return results

    def copy_to_workbench(self, handle: WorkbenchHandle, host_path: str, container_path: str) -> None:
        """Copy a file from the host into the workbench container."""
        result = subprocess.run(
            ["docker", "cp", host_path, f"{handle.container_name}:{container_path}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"docker cp failed: {result.stderr.strip() or result.stdout.strip()}")


# ================================================
# Helpers
# ================================================


def _dind_volume_name(ree_id: str) -> str:
    """Volume backing the workbench's in-container ``/var/lib/docker``.

    Kept off the container's overlayfs rootfs so the nested daemon can use the
    overlay2 storage driver (copy-on-write) instead of falling back to vfs.
    """
    return f"repo2ree-dind-{ree_id}"


def _docker(*args: str) -> None:
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")


def _docker_silent(*args: str) -> None:
    """Like _docker but ignores failures (for cleanup paths)."""
    subprocess.run(["docker", *args], capture_output=True)


def _docker_exec(container: str, *argv: str) -> None:
    result = subprocess.run(
        ["docker", "exec", container, *argv],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker exec {argv[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
