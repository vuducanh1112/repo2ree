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
import subprocess
from dataclasses import dataclass

from repo2ree_core.container.run_script import LogSink
from repo2ree_protocol.command import Command
from repo2ree_protocol.result import ActionResult
from repo2ree_api.workbench.registry import WorkbenchEntry, WorkbenchRegistry


@dataclass(frozen=True)
class WorkbenchHandle:
    ree_id: str
    container_name: str
    volume_name: str

    @classmethod
    def from_entry(cls, entry: WorkbenchEntry) -> "WorkbenchHandle":
        return cls(
            ree_id=entry.ree_id,
            container_name=entry.container_name,
            volume_name=entry.volume_name,
        )


class WorkbenchManager:
    def __init__(
        self,
        registry: WorkbenchRegistry,
        workbench_image: str,
    ):
        self._registry = registry
        self._image = workbench_image

    # ------------------------------------------------
    # Lifecycle
    # ------------------------------------------------

    def provision(self, ree_id: str, name: str) -> WorkbenchHandle:
        """Create volume + container, initialise the REE, register handle."""
        volume_name = f"repo2ree-ree-{ree_id}"
        container_name = f"repo2ree-wb-{ree_id}"

        _docker("volume", "create", volume_name)

        _docker(
            "run",
            "-d",
            "--privileged",
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            "-v",
            f"{volume_name}:/ree",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            self._image,
            "sleep",
            "infinity",
        )

        _docker_exec(
            container_name,
            "repo2ree",
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
            "-v",
            f"{entry.volume_name}:/ree",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            self._image,
            "sleep",
            "infinity",
        )
        return WorkbenchHandle.from_entry(entry)

    def teardown(self, handle: WorkbenchHandle) -> None:
        """Stop + remove the container and its volume, unregister."""
        _docker_silent("rm", "-f", handle.container_name)
        _docker_silent("volume", "rm", handle.volume_name)
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
            import logging

            logging.getLogger(__name__).warning(
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
        cmd_json = cmd.model_dump_json()

        proc = subprocess.Popen(
            [
                "docker",
                "exec",
                "-i",
                handle.container_name,
                "repo2ree",
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

        assert proc.stdin is not None
        assert proc.stdout is not None
        assert proc.stderr is not None

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

        if stdout:
            try:
                return ActionResult.model_validate_json(stdout)
            except Exception:
                pass

        return ActionResult(status="failed", exit_code=proc.returncode or 1)

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: WorkbenchHandle, *argv: str) -> bytes:
        """Run a read-only CLI subcommand and return its stdout bytes."""
        result = subprocess.run(
            ["docker", "exec", handle.container_name, "repo2ree", *argv],
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            stdout = result.stdout.decode(errors="replace").strip()
            detail = stderr or stdout or "(no output on stdout/stderr)"
            raise RuntimeError(
                f"query {argv!r} failed (exit {result.returncode}): {detail}"
            )
        return result.stdout

    def get_ree_metadata(self, handle: WorkbenchHandle) -> dict:  # type: ignore[type-arg]
        raw = self.dispatch_query(handle, "get-ree")
        return json.loads(raw)

    def get_workspace(self, handle: WorkbenchHandle) -> dict:  # type: ignore[type-arg]
        raw = self.dispatch_query(handle, "get-workspace")
        return json.loads(raw)

    def read_file_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-file", "--path", path)

    def read_artifact_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-artifact", "--path", path)

    def build_archive(self, handle: WorkbenchHandle) -> bytes:
        return self.dispatch_query(handle, "build-archive")

    def list_all_metadata(self) -> list[dict]:  # type: ignore[type-arg]
        """Return metadata for every registered workbench, skipping unreachable ones."""
        results = []
        for entry in self._registry.list_all():
            handle = WorkbenchHandle.from_entry(entry)
            if not self._is_running(handle.container_name):
                continue
            try:
                results.append(self.get_ree_metadata(handle))
            except Exception:
                pass
        results.sort(key=lambda m: m.get("updatedAt", ""), reverse=True)
        return results

    def copy_to_workbench(
        self, handle: WorkbenchHandle, host_path: str, container_path: str
    ) -> None:
        """Copy a file from the host into the workbench container."""
        result = subprocess.run(
            ["docker", "cp", host_path, f"{handle.container_name}:{container_path}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"docker cp failed: {result.stderr.strip() or result.stdout.strip()}"
            )


# ------------------------------------------------
# Helpers
# ------------------------------------------------


def _docker(*args: str) -> None:
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"docker {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}"
        )


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
        raise RuntimeError(
            f"docker exec {argv[0]} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
