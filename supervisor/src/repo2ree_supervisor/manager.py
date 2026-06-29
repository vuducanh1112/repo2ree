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
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from repo2ree_protocol.command import Command
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    SpanSink,
    command_metric_attrs,
    current_traceparent,
    get_meter,
    get_tracer,
    record_command_status,
    record_ree_id,
)
from repo2ree_supervisor.registry import WorkbenchEntry, WorkbenchRegistry

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)

# ================================================
# Metrics
# ================================================

_container_gone_counter = _meter.create_counter(
    "workbench.container_gone",
    description="Number of docker exec failures due to container gone or stopping.",
)
_reprovision_counter = _meter.create_counter(
    "workbench.reprovision",
    description="Number of workbench container reprovisioning operations.",
)
_exec_duration = _meter.create_histogram(
    "workbench.execute_duration_seconds",
    description="Wall-clock duration of workbench command execution (lock held, docker exec running).",
    unit="s",
)
_lock_wait_duration = _meter.create_histogram(
    "workbench.lock_wait_seconds",
    description="Time a dispatch blocked on the per-REE lock before execution (another run in progress).",
    unit="s",
)

# ================================================
# Constants
# ================================================


# Exit codes from `docker exec` that mean the container is gone / stopping.
# 137 = killed by SIGKILL (container OOM-killed or being removed)
# 126 = OCI runtime exec failed (container shutting down, broken init pipe)
_CONTAINER_GONE_EXIT_CODES = frozenset({126, 137})
_WORKBENCH_DOCKER_MODES = frozenset({"dind", "host-socket"})
_HOST_DOCKER_SOCK_MOUNT = "/var/run/docker.sock:/var/run/docker.sock"


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
    image: str = ""

    @classmethod
    def from_entry(cls, entry: WorkbenchEntry) -> WorkbenchHandle:
        return cls(
            ree_id=entry.ree_id,
            container_name=entry.container_name,
            volume_name=entry.volume_name,
            image=entry.image,
        )


# ================================================
# Manager
# ================================================


class WorkbenchManager:
    def __init__(
        self,
        registry: WorkbenchRegistry,
        workbench_image: str,
        span_sink: SpanSink | None = None,
        workbench_docker_mode: str = "dind",
    ):
        if workbench_docker_mode not in _WORKBENCH_DOCKER_MODES:
            modes = ", ".join(sorted(_WORKBENCH_DOCKER_MODES))
            raise ValueError(f"unknown workbench docker mode {workbench_docker_mode!r}; expected one of: {modes}")
        self._registry = registry
        self._image = workbench_image
        self._span_sink = span_sink
        self._docker_mode = workbench_docker_mode
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

    def provision(
        self,
        ree_id: str,
        name: str,
        log: LogSink | None = None,
        image: str | None = None,
    ) -> WorkbenchHandle:
        """Create volume + container, initialise the REE, register handle.

        ``image`` overrides the manager's default workbench image for this REE.
        """
        with tracer.start_as_current_span("workbench.provision") as span:
            record_ree_id(span, ree_id)
            volume_name = f"repo2ree-ree-{ree_id}"
            dind_volume_name = _dind_volume_name(ree_id)
            container_name = f"repo2ree-wb-{ree_id}"

            resolved_image = image or self._image

            _docker("volume", "create", volume_name)
            if self._docker_mode == "dind":
                _docker("volume", "create", dind_volume_name)

            self._run_workbench_container(container_name, ree_id, volume_name, log=log, image=resolved_image)

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
                image=resolved_image,
            )
            self._registry.register(entry)
            return WorkbenchHandle.from_entry(entry)

    def reprovision(self, ree_id: str, log: LogSink | None = None) -> WorkbenchHandle:
        """Replace the container with a fresh one from the same image, keeping the volume."""
        _reprovision_counter.add(1)
        with tracer.start_as_current_span("workbench.reprovision") as span:
            record_ree_id(span, ree_id)
            entry = self._registry.lookup(ree_id)
            if entry is None:
                raise KeyError(f"no workbench registered for {ree_id}")
            _docker_silent("rm", "-f", entry.container_name)
            # Reprovision from the REE's own image, not the manager default —
            # ``entry.image`` is empty only for pre-image-tracking entries, where
            # falling back to the default is the best we can do.
            self._run_workbench_container(
                entry.container_name, entry.ree_id, entry.volume_name, log=log, image=entry.image or None
            )
            return WorkbenchHandle.from_entry(entry)

    def teardown(self, handle: WorkbenchHandle) -> None:
        """Stop + remove the container and its volumes, unregister."""
        with tracer.start_as_current_span("workbench.teardown") as span:
            record_ree_id(span, handle.ree_id)
            _docker_silent("rm", "-f", handle.container_name)
            _docker_silent("volume", "rm", handle.volume_name)
            if self._docker_mode == "dind":
                _docker_silent("volume", "rm", _dind_volume_name(handle.ree_id))
            self._registry.unregister(handle.ree_id)

    def _run_workbench_container(
        self,
        container_name: str,
        ree_id: str,
        volume_name: str,
        log: LogSink | None = None,
        image: str | None = None,
    ) -> None:
        image = image or self._image
        # Always pull up front so a moving tag (e.g. ``:edge``) picks up newer
        # builds instead of being pinned to whatever was first cached — and pull
        # explicitly (not via ``docker run``'s implicit pull) so the progress
        # streams live rather than being buffered and dropped under
        # capture_output. ``docker pull`` is incremental: it only transfers
        # changed layers and is cheap when already current.
        #
        # Offline / local-only fallback: if the pull fails but the image is
        # already present locally (no network, or a locally-built image with no
        # registry origin like the e2e test image), warn and provision from the
        # cached copy instead of failing.
        try:
            _docker_stream("pull", image, log=log, timeout=600)
        except RuntimeError as exc:
            if not _image_present(image):
                raise
            message = f"pull failed ({exc}); using cached image {image}"
            logger.warning(message)
            if log is not None:
                log("system", "warn", message)
        _docker(
            "run",
            "-d",
            *self._docker_backend_args(ree_id),
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            "-v",
            f"{volume_name}:/ree",
            image,
            "sleep",
            "infinity",
            timeout=120,
        )

    def _docker_backend_args(self, ree_id: str) -> list[str]:
        if self._docker_mode == "dind":
            # No host docker.sock mount: the workbench runs its own in-container
            # daemon for per-REE isolation. /var/lib/docker is volume-backed so
            # the nested daemon uses overlay2, not vfs.
            return [
                "--privileged",
                "-e",
                "DOCKER_DRIVER=overlay2",
                "-v",
                f"{_dind_volume_name(ree_id)}:/var/lib/docker",
            ]
        return [
            "-v",
            _HOST_DOCKER_SOCK_MOUNT,
            "-e",
            "DOCKER_HOST=unix:///var/run/docker.sock",
            "-e",
            "WORKBENCH_DOCKER_MODE=host-socket",
        ]

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
            timeout=10,
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
        with tracer.start_as_current_span("workbench.dispatch_action") as span:
            CommandSpanAttrs(operation=str(cmd.operation), run_id=run_id, ree_id=handle.ree_id).apply(span)
            # Time spent blocked here is per-REE lock contention (another run in
            # progress); record it on acquisition so wait is a first-class metric
            # rather than something inferred from the dispatch/execute span gap.
            _lock_t0 = time.monotonic()
            with self._ree_lock(handle.ree_id):
                _lock_wait_duration.record(
                    time.monotonic() - _lock_t0,
                    command_metric_attrs(str(cmd.operation)),
                )
                with tracer.start_as_current_span("workbench.execute"):
                    _t0 = time.monotonic()
                    result = self._dispatch_action_locked(handle, cmd, run_id, log)
                    _exec_duration.record(
                        time.monotonic() - _t0,
                        command_metric_attrs(str(cmd.operation), status=result.status),
                    )
            record_command_status(span, result.status)
            return result

    def _dispatch_action_locked(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
    ) -> ActionResult:
        cmd_json = cmd.model_dump_json()

        # Carry the active trace context into the executor so its spans hang
        # under this dispatch span. When the API injected a span_sink, ask the
        # executor to relay its spans back over stderr (it has no path to the
        # collector itself); we forward them after the command completes.
        trace_env: list[str] = []
        traceparent = current_traceparent()
        if traceparent:
            trace_env += ["-e", f"TRACEPARENT={traceparent}"]
        if self._span_sink is not None:
            trace_env += ["-e", "TRACE_RELAY=1"]

        proc = subprocess.Popen(
            [
                "docker",
                "exec",
                "-i",
                *trace_env,
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

        # Stream stderr log events live; hand relayed span events to the sink as
        # they arrive (not buffered to the end) so a command that hangs or gets
        # killed still ships the spans it emitted before stalling — exactly the
        # case a trace is most useful. The sink is non-blocking (it enqueues for
        # a background forwarder), so the actual export never sits on this loop,
        # the per-REE lock, or the measured execute window.
        for raw_line in proc.stderr:
            line = raw_line.rstrip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                log("system", "info", line)
                continue
            event_type = event.get("type")
            if event_type == "log":
                log(event["stream"], event["level"], event["message"])
            elif event_type == "span" and self._span_sink is not None:
                self._span_sink([event["payload"]])

        stdout = proc.stdout.read().strip()
        proc.wait()

        if proc.returncode in _CONTAINER_GONE_EXIT_CODES:
            _container_gone_counter.add(1, command_metric_attrs(str(cmd.operation)))
            raise WorkbenchUnavailableError(f"docker exec exited {proc.returncode} — container gone or stopping")

        if stdout:
            with suppress(Exception):
                return ActionResult.model_validate_json(stdout)

        return ActionResult(status="failed", exit_code=proc.returncode or 1)

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: WorkbenchHandle, *argv: str, locked: bool = False) -> bytes:
        """Run a read-only CLI subcommand and return its stdout bytes.

        Set ``locked`` for queries that must observe a consistent snapshot — they
        take the per-REE lock so no mutating action runs concurrently. Plain reads
        leave it off and run unsynchronised.
        """
        if locked:
            with self._ree_lock(handle.ree_id):
                return self._dispatch_query(handle, *argv)
        return self._dispatch_query(handle, *argv)

    def _dispatch_query(self, handle: WorkbenchHandle, *argv: str) -> bytes:
        result = subprocess.run(
            ["docker", "exec", handle.container_name, "repo2ree-exec", *argv],
            capture_output=True,
            timeout=30,
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

    def image_for(self, handle: WorkbenchHandle) -> str:
        """The image this REE's workbench runs, falling back to the manager default."""
        return handle.image or self._image

    def read_file_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-file", "--path", path)

    def read_artifact_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-artifact", "--path", path)

    def build_archive(self, handle: WorkbenchHandle) -> bytes:
        return self.dispatch_query(handle, "build-archive", locked=True)

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
            timeout=30,
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


def _docker(*args: str, timeout: int = 60) -> None:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")


def _image_present(image: str) -> bool:
    """True if the image already exists locally (no registry round-trip)."""
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=30).returncode == 0


def _docker_stream(*args: str, log: LogSink | None = None, timeout: int = 600) -> None:
    """Run a docker command, streaming its output live instead of buffering it.

    Docker writes progress (pull layers, etc.) to stderr and only renders the
    animated bars when attached to a TTY — here it's a pipe, so we get plain
    line-by-line progress, which is what belongs in a log. Lines go to ``log``
    when a sink is provided, otherwise to the supervisor logger.
    """
    proc = subprocess.Popen(
        ["docker", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if proc.stdout is None:
        raise RuntimeError("Popen stdout unavailable")
    try:
        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            if log is not None:
                log("system", "info", line)
            else:
                logger.info("docker %s: %s", args[0], line)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            # Don't leave the pull running; normalise to RuntimeError so callers
            # handle a hang the same as any other pull failure.
            proc.kill()
            proc.wait()
            raise RuntimeError(f"docker {args[0]} timed out after {timeout}s") from exc
    finally:
        proc.stdout.close()
    if proc.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed (exit {proc.returncode})")


def _docker_silent(*args: str) -> None:
    """Like _docker but ignores failures (for cleanup paths)."""
    with suppress(Exception):
        subprocess.run(["docker", *args], capture_output=True, timeout=30)


def _docker_exec(container: str, *argv: str) -> None:
    result = subprocess.run(
        ["docker", "exec", container, *argv],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker exec {argv[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
