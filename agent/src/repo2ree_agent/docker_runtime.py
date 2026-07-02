"""Docker-backed workbench runtime — the agent's only runtime today.

This owns everything the control plane used to shell out for: provisioning
volumes + containers, dind vs host-socket daemon modes, container/volume
naming, the pull-with-cache fallback, streaming executor logs, and the
``docker exec`` exit codes that mean the container is gone. It emits the
protocol's ``AgentFrame`` records for streaming calls and raises
``WorkbenchGone`` for request/response calls when the backend has vanished.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterator

from repo2ree_protocol.agent import (
    AgentFrame,
    DoneFrame,
    ErrorFrame,
    LocationFrame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
    WorkbenchLocation,
)
from repo2ree_protocol.result import ActionResult

logger = logging.getLogger(__name__)

# Exit codes from `docker exec` that mean the container is gone / stopping.
# 137 = killed by SIGKILL (container OOM-killed or being removed)
# 126 = OCI runtime exec failed (container shutting down, broken init pipe)
_CONTAINER_GONE_EXIT_CODES = frozenset({126, 137})
_WORKBENCH_DOCKER_MODES = frozenset({"dind", "host-socket"})
_HOST_DOCKER_SOCK_MOUNT = "/var/run/docker.sock:/var/run/docker.sock"


class WorkbenchGone(RuntimeError):
    """The workbench backend is gone or stopping (a request/response call)."""


class DockerRuntime:
    def __init__(self, docker_mode: str = "dind"):
        if docker_mode not in _WORKBENCH_DOCKER_MODES:
            modes = ", ".join(sorted(_WORKBENCH_DOCKER_MODES))
            raise ValueError(f"unknown workbench docker mode {docker_mode!r}; expected one of: {modes}")
        self._docker_mode = docker_mode

    # ------------------------------------------------
    # Naming — deterministic from ree_id, a local-docker convention.
    # ------------------------------------------------

    @staticmethod
    def _container_name(ree_id: str) -> str:
        return f"repo2ree-wb-{ree_id}"

    @staticmethod
    def _volume_name(ree_id: str) -> str:
        return f"repo2ree-ree-{ree_id}"

    @staticmethod
    def _dind_volume_name(ree_id: str) -> str:
        """Volume backing the workbench's in-container ``/var/lib/docker``.

        Kept off the container's overlayfs rootfs so the nested daemon can use the
        overlay2 storage driver (copy-on-write) instead of falling back to vfs.
        """
        return f"repo2ree-dind-{ree_id}"

    # ------------------------------------------------
    # Lifecycle (streaming)
    # ------------------------------------------------

    def provision(self, ree_id: str, image: str) -> Iterator[AgentFrame]:
        container_name = self._container_name(ree_id)
        volume_name = self._volume_name(ree_id)
        try:
            _docker("volume", "create", volume_name)
            if self._docker_mode == "dind":
                _docker("volume", "create", self._dind_volume_name(ree_id))
            yield from self._run_workbench_container(container_name, ree_id, volume_name, image)
        except RuntimeError as exc:
            yield ErrorFrame(detail=str(exc))
            return
        yield LocationFrame(location=WorkbenchLocation(container_name=container_name, volume_name=volume_name))

    def reprovision(self, ree_id: str, location: WorkbenchLocation, image: str) -> Iterator[AgentFrame]:
        try:
            _docker_silent("rm", "-f", location.container_name)
            yield from self._run_workbench_container(location.container_name, ree_id, location.volume_name, image)
        except RuntimeError as exc:
            yield ErrorFrame(detail=str(exc))
            return
        yield DoneFrame()

    def remove(self, ree_id: str, location: WorkbenchLocation) -> None:
        _docker_silent("rm", "-f", location.container_name)
        _docker_silent("volume", "rm", location.volume_name)
        if self._docker_mode == "dind":
            _docker_silent("volume", "rm", self._dind_volume_name(ree_id))

    def _run_workbench_container(
        self, container_name: str, ree_id: str, volume_name: str, image: str
    ) -> Iterator[AgentFrame]:
        # Always pull up front so a moving tag (e.g. ``:edge``) picks up newer
        # builds instead of being pinned to whatever was first cached — and pull
        # explicitly so the progress streams live. ``docker pull`` is
        # incremental: it only transfers changed layers and is cheap when current.
        #
        # Offline / local-only fallback: if the pull fails but the image is
        # already present locally (no network, or a locally-built image with no
        # registry origin like the e2e test image), warn and provision from the
        # cached copy instead of failing.
        try:
            for line in _docker_stream_lines("pull", image, timeout=600):
                yield LogFrame(stream="system", level="info", message=line)
        except RuntimeError as exc:
            if not _image_present(image):
                raise
            message = f"pull failed ({exc}); using cached image {image}"
            logger.warning(message)
            yield LogFrame(stream="system", level="warn", message=message)
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
                f"{self._dind_volume_name(ree_id)}:/var/lib/docker",
            ]
        return [
            "-v",
            _HOST_DOCKER_SOCK_MOUNT,
            "-e",
            "DOCKER_HOST=unix:///var/run/docker.sock",
            "-e",
            "WORKBENCH_DOCKER_MODE=host-socket",
        ]

    # ------------------------------------------------
    # Queries / simple exec (request/response)
    # ------------------------------------------------

    def is_running(self, container_name: str) -> bool:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def exec_simple(self, container_name: str, argv: list[str], timeout: int = 60) -> None:
        self._exec(container_name, argv, timeout, what=f"docker exec {argv[0]}")

    def exec_query(self, container_name: str, argv: list[str], timeout: int = 30) -> bytes:
        return self._exec(container_name, argv, timeout, what=f"query {argv!r}")

    @staticmethod
    def _exec(container_name: str, argv: list[str], timeout: int, what: str) -> bytes:
        """Run ``argv`` in the container and return its stdout bytes.

        Raises ``WorkbenchGone`` when the failure means the container is gone or
        stopping, ``RuntimeError`` for any other non-zero exit."""
        result = subprocess.run(
            ["docker", "exec", container_name, *argv],
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            stdout = result.stdout.decode(errors="replace").strip()
            detail = stderr or stdout or "(no output on stdout/stderr)"
            message = f"{what} failed (exit {result.returncode}): {detail}"
            if result.returncode in _CONTAINER_GONE_EXIT_CODES or "No such container" in detail:
                raise WorkbenchGone(message)
            raise RuntimeError(message)
        return result.stdout

    def copy_in(self, container_name: str, source_path: str, container_path: str) -> None:
        # ``source_path`` is a file on *our* host — the control plane streamed the
        # bytes here into a local temp file (see TransferStore), so there is no
        # shared-filesystem assumption with the control plane. ``docker cp``
        # resolves the destination path the same way it always has.
        result = subprocess.run(
            ["docker", "cp", source_path, f"{container_name}:{container_path}"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"docker cp failed: {result.stderr.strip() or result.stdout.strip()}")

    # ------------------------------------------------
    # Action dispatch (streaming)
    # ------------------------------------------------

    def exec_action(self, container_name: str, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[AgentFrame]:
        env_args: list[str] = []
        for key, value in env.items():
            env_args += ["-e", f"{key}={value}"]

        proc = subprocess.Popen(
            [
                "docker",
                "exec",
                "-i",
                *env_args,
                container_name,
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

        # The executor emits NDJSON log/span events on stderr; forward each as a
        # typed frame the moment it arrives (a hung/killed command still ships the
        # frames it emitted before stalling — the case a trace is most useful).
        for raw_line in proc.stderr:
            line = raw_line.rstrip()
            if not line:
                continue
            frame = _executor_line_to_frame(line)
            if frame is not None:
                yield frame

        stdout = proc.stdout.read().strip()
        proc.wait()

        if proc.returncode in _CONTAINER_GONE_EXIT_CODES:
            yield UnavailableFrame(detail=f"docker exec exited {proc.returncode} — container gone or stopping")
            return

        yield ResultFrame(result=_parse_action_result(stdout, proc.returncode or 0))


# ================================================
# Helpers
# ================================================


def _executor_line_to_frame(line: str) -> AgentFrame | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return LogFrame(stream="system", level="info", message=line)
    event_type = event.get("type")
    if event_type == "log":
        return LogFrame(stream=event["stream"], level=event["level"], message=event["message"])
    if event_type == "span":
        return SpanFrame(payload=event["payload"])
    return LogFrame(stream="system", level="info", message=line)


def _parse_action_result(stdout: str, returncode: int) -> ActionResult:
    if stdout:
        try:
            return ActionResult.model_validate_json(stdout)
        except ValueError:
            pass
    return ActionResult(status="failed", exit_code=returncode or 1)


def _docker(*args: str, timeout: int = 60) -> None:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")


def _image_present(image: str) -> bool:
    """True if the image already exists locally (no registry round-trip)."""
    return subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=30).returncode == 0


def _docker_stream_lines(*args: str, timeout: int = 600) -> Iterator[str]:
    """Run a docker command, yielding its output line-by-line as it arrives.

    Docker writes progress (pull layers, etc.) to stderr and only renders the
    animated bars when attached to a TTY — here it's a pipe, so we get plain
    line-by-line progress, which is what belongs in a log. Raises RuntimeError on
    a non-zero exit or a timeout so callers handle a hang like any other failure.
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
            if line:
                yield line
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            proc.kill()
            proc.wait()
            raise RuntimeError(f"docker {args[0]} timed out after {timeout}s") from exc
    finally:
        proc.stdout.close()
    if proc.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed (exit {proc.returncode})")


def _docker_silent(*args: str) -> None:
    """Like _docker but ignores failures (for cleanup paths)."""
    try:
        subprocess.run(["docker", *args], capture_output=True, timeout=30)
    except (subprocess.SubprocessError, OSError):
        pass
