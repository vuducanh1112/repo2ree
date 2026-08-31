"""Docker-backed workbench runtime — the agent's only runtime today.

This owns everything the control plane used to shell out for: provisioning
volumes + containers, dind vs host-socket daemon modes, container/volume
naming, the pull-with-cache fallback, streaming executor logs, and the
``docker exec`` exit codes that mean the container is gone. It emits the
protocol's ``AgentFrame`` records for streaming calls and raises
``WorkbenchGoneError`` for request/response calls when the backend has vanished.

Executor injection: when the agent ships an executor bundle (the
``REPO2REE_EXEC_BUNDLE`` dir — see nix/exec-bundle.nix), benches don't need
``repo2ree-exec`` baked into their image. The runtime populates a
content-addressed volume with the bundle's nix closure once per host, mounts
it read-only at ``/nix/store`` in every bench, and drives the executor via
the manifest's absolute path — carried in the minted ``WorkbenchRef`` token
so later calls use it without re-deciding. Images that carry their own
``/nix`` (nix-built images) are detected and left un-injected: mounting over
their ``/nix/store`` would shadow everything they contain, and they must
provide ``repo2ree-exec`` on PATH themselves.

The bench's main process is the image's own default command — the env image
defines the environment, daemons included (docker:dind's entrypoint starts
``dockerd`` only when dockerd is the command). A pause command (the bundle's
static sleep, or the image's own) is strictly the rescue for images whose
default process exits immediately.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import threading
import time
from collections.abc import Generator, Iterator
from contextlib import contextmanager

from repo2ree_agent.executor import frames as executor_frames
from repo2ree_agent.runtimes.base import WorkbenchGoneError
from repo2ree_agent.runtimes.docker import cli as docker_cli
from repo2ree_agent.runtimes.docker.injection import InjectionBundle, load_injection_bundle
from repo2ree_agent.runtimes.docker.reference import (
    DockerWorkbenchHandle,
    decode_reference,
    encode_reference,
)
from repo2ree_protocol.agent import (
    AgentFrame,
    DockerWorkbenchSpec,
    ErrorFrame,
    LogFrame,
    ResultFrame,
    UnavailableFrame,
    WorkbenchRef,
    WorkbenchRefFrame,
)
from repo2ree_protocol.tracing import (
    command_metric_attrs,
    current_traceparent,
    get_meter,
    get_tracer,
    record_command_status,
)

__all__ = ["DockerRuntime", "WorkbenchGoneError"]

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)

_docker_operation_duration = _meter.create_histogram(
    "agent.docker_operation_duration_seconds",
    description="Wall-clock duration of Docker CLI operations performed by the agent.",
    unit="s",
)
_docker_operation_counter = _meter.create_counter(
    "agent.docker_operation",
    description="Number of Docker CLI operations performed by the agent.",
)
_workbench_gone_counter = _meter.create_counter(
    "agent.workbench_gone",
    description="Number of Docker operations that found the target workbench gone or stopping.",
)

_WORKBENCH_DOCKER_MODES = frozenset({"dind", "host-socket"})
_HOST_DOCKER_SOCK_MOUNT = "/var/run/docker.sock:/var/run/docker.sock"
_RESOURCE_OWNER_ENV = "REPO2REE_RESOURCE_OWNER"
_RESOURCE_OWNER_LABEL = "repo2ree.resource-owner"

# Where the injected closure appears inside a bench. The bundle's paths are
# absolute into /nix/store, so this is not a choice — it is the mount point
# that makes them resolve.
_STORE_MOUNT = "/nix/store"
# Marker file at the store volume's root: present only after a populate
# finished, so a crash mid-copy is retried rather than trusted.
_POPULATED_SENTINEL = ".repo2ree-populated"
# How long a freshly started bench must stay up before it counts as viable.
# Long enough to catch a default command that exits at once (alpine's detached
# /bin/sh); daemon *readiness* (dockerd accepting connections) is not gated
# here — the process staying alive is the contract.
_STARTUP_GRACE_SECONDS = 2.0


class DockerRuntime:
    runtime_name = "docker"

    def __init__(
        self,
        docker_mode: str = "dind",
        exec_bundle_dir: str | None = None,
        tools_bundle_dir: str | None = None,
    ):
        if docker_mode not in _WORKBENCH_DOCKER_MODES:
            modes = ", ".join(sorted(_WORKBENCH_DOCKER_MODES))
            raise ValueError(f"unknown workbench docker mode {docker_mode!r}; expected one of: {modes}")
        self._docker_mode = docker_mode
        # Test stacks set this to a unique run token. Labels let their teardown
        # select only resources that run created, while ordinary deployments
        # leave resources unlabelled and retain their existing lifecycle.
        self._resource_owner = os.environ.get(_RESOURCE_OWNER_ENV, "").strip()
        self._bundle = load_injection_bundle(
            exec_bundle_dir if exec_bundle_dir is not None else os.environ.get("REPO2REE_EXEC_BUNDLE") or None,
            tools_bundle_dir if tools_bundle_dir is not None else os.environ.get("REPO2REE_TOOLS_BUNDLE") or None,
        )
        # Populating the store volume is once-per-content-hash; the lock keeps
        # concurrent provisions from racing the copy, the set makes the common
        # case (already populated this process) free.
        self._populate_lock = threading.Lock()
        self._populated_volumes: set[str] = set()

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

    def _resource_label_args(self) -> list[str]:
        if not self._resource_owner:
            return []
        return ["--label", f"{_RESOURCE_OWNER_LABEL}={self._resource_owner}"]

    def _create_workbench_volume(self, name: str) -> None:
        _docker("volume", "create", *self._resource_label_args(), name)

    # ------------------------------------------------
    # Lifecycle (streaming)
    # ------------------------------------------------

    def provision(self, ree_id: str, spec: DockerWorkbenchSpec) -> Iterator[AgentFrame]:
        container_name = self._container_name(ree_id)
        volume_name = self._volume_name(ree_id)
        image = spec.base_image
        with _docker_op("provision") as op:
            try:
                self._create_workbench_volume(volume_name)
                if self._docker_mode == "dind":
                    self._create_workbench_volume(self._dind_volume_name(ree_id))
                exec_path = yield from self._run_workbench_container(container_name, ree_id, volume_name, image)
            except RuntimeError as exc:
                op.status = "failed"
                # Provision has not emitted a reference yet, so the supervisor
                # cannot compensate this partial creation. Reclaim every
                # deterministic resource here before returning the error frame.
                _docker_silent("rm", "-f", "-v", container_name)
                _docker_silent("volume", "rm", volume_name)
                if self._docker_mode == "dind":
                    _docker_silent("volume", "rm", self._dind_volume_name(ree_id))
                yield ErrorFrame(detail=str(exc))
                return
            yield WorkbenchRefFrame(
                ref=encode_reference(
                    DockerWorkbenchHandle(
                        ree_id=ree_id,
                        container_name=container_name,
                        volume_name=volume_name,
                        exec_path=exec_path,
                    )
                )
            )

    def reprovision(self, ref: WorkbenchRef, spec: DockerWorkbenchSpec) -> Iterator[AgentFrame]:
        handle = decode_reference(ref)
        with _docker_op("reprovision") as op:
            try:
                _docker_silent("rm", "-f", "-v", handle.container_name)
                exec_path = yield from self._run_workbench_container(
                    handle.container_name, handle.ree_id, handle.volume_name, spec.base_image
                )
            except RuntimeError as exc:
                op.status = "failed"
                yield ErrorFrame(detail=str(exc))
                return
            # A fresh reference, not a done: injection may have changed the
            # executor path encoded in the runtime-private token.
            yield WorkbenchRefFrame(ref=encode_reference(handle.model_copy(update={"exec_path": exec_path})))

    def remove(self, ref: WorkbenchRef) -> None:
        handle = decode_reference(ref)
        with _docker_op("remove"):
            # -v drops the anonymous volumes the image declared (docker:dind
            # declares /var/lib/docker and /certs, so every bench would leave
            # unreclaimable hex-named volumes behind). Named volumes — ours,
            # below — are never touched by it, which is why every `rm` here
            # carries it.
            _docker_remove("rm", "-f", "-v", handle.container_name)
            _docker_remove("volume", "rm", handle.volume_name)
            if self._docker_mode == "dind":
                _docker_remove("volume", "rm", self._dind_volume_name(handle.ree_id))
            # The injected store volume is shared across benches and content-
            # addressed — never removed per REE.

    def _run_workbench_container(
        self, container_name: str, ree_id: str, volume_name: str, image: str
    ) -> Generator[AgentFrame, None, str]:
        """Pull ``image`` and start the bench; returns the executor entry point.

        A generator with a return value: frames stream out, the exec path (the
        bundle's absolute entry point when injecting, the PATH default when the
        image carries its own executor) comes back via ``yield from``.
        """
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

        bundle = None
        if self._bundle is not None:
            if _image_has_nix(image):
                yield LogFrame(
                    stream="system",
                    level="info",
                    message=f"image {image} ships its own /nix — skipping executor injection, using PATH",
                )
            else:
                bundle = self._bundle

        injection_args: list[str] = []
        exec_path = "repo2ree-exec"
        if bundle is not None:
            yield from self._ensure_store_volume(image, bundle)
            injection_args = ["-v", f"{bundle.volume_name}:{_STORE_MOUNT}:ro"]
            for key, value in sorted(bundle.tool_env.items()):
                injection_args += ["-e", f"{key}={value}"]
            exec_path = bundle.exec_path

        run_args = [
            *self._docker_backend_args(ree_id),
            *injection_args,
            *self._resource_label_args(),
            "--name",
            container_name,
            # tini as PID 1: whatever keeps the bench alive, docker exec'd
            # process trees get reaped instead of accumulating zombies.
            "--init",
            "-v",
            f"{volume_name}:/ree",
        ]
        # The image's own default process is the bench's main process — the env
        # image defines the environment, including its daemons (docker:dind's
        # entrypoint only starts dockerd when dockerd *is* the command, so
        # forcing a keep-alive command of our own would boot it substrate-dead).
        # A pause command is strictly the rescue for images whose default exits
        # immediately (alpine's detached /bin/sh, distroless with no CMD).
        if not self._start_bench(container_name, run_args, image, command=[]):
            fallback = [bundle.pause_path, "infinity"] if bundle is not None else ["sleep", "infinity"]
            yield LogFrame(
                stream="system",
                level="info",
                message=f"image {image}'s default process exited immediately;"
                f" keeping the bench alive with {fallback[0]}",
            )
            if not self._start_bench(container_name, run_args, image, command=fallback):
                raise RuntimeError(
                    f"bench container from {image} would not stay running (default command and fallback both exited)"
                )
        yield from _probe_bench(container_name, exec_path, image)
        return exec_path

    @staticmethod
    def _start_bench(container_name: str, run_args: list[str], image: str, command: list[str]) -> bool:
        """Start the bench and report whether it stayed up past the grace window.

        The restart policy is applied only *after* the container proves viable —
        starting with ``--restart unless-stopped`` would turn an exits-immediately
        default command into a silent crash loop instead of a falsifiable check.
        A failed attempt is removed so the retry can reuse the name.
        """
        _docker("run", "-d", *run_args, image, *command, timeout=120)
        time.sleep(_STARTUP_GRACE_SECONDS)
        # The grace check is a falsifiable "did it stay up"; an indeterminate
        # probe is not proof it did, so treat it as this attempt not being
        # viable (fall back / retry) rather than promoting an unconfirmed bench.
        try:
            stayed_up = _container_running(container_name)
        except ContainerStateUnknownError:
            stayed_up = False
        if not stayed_up:
            _docker_silent("rm", "-f", "-v", container_name)
            return False
        _docker("update", "--restart", "unless-stopped", container_name)
        return True

    def _ensure_store_volume(self, image: str, bundle: InjectionBundle) -> Iterator[AgentFrame]:
        """Populate the content-addressed store volume, once.

        The copies go through a never-started scratch container from ``image``
        (just pulled, so no extra fetch) with the volume mounted — ``docker cp``
        addresses paths inside a container, running or not.
        """
        if bundle.volume_name in self._populated_volumes:
            return
        with self._populate_lock:
            if bundle.volume_name in self._populated_volumes:
                return
            _docker("volume", "create", bundle.volume_name)
            scratch = _docker_out("create", "-v", f"{bundle.volume_name}:/bundle-store", image, "/repo2ree-noop")
            try:
                if _container_path_exists(scratch, f"/bundle-store/{_POPULATED_SENTINEL}"):
                    self._populated_volumes.add(bundle.volume_name)
                    return
                yield LogFrame(
                    stream="system",
                    level="info",
                    message=f"populating executor volume {bundle.volume_name}"
                    f" ({len(bundle.store_sources)} closure paths)",
                )
                for source in bundle.store_sources:
                    _docker("cp", source, f"{scratch}:/bundle-store", timeout=600)
                with tempfile.NamedTemporaryFile(prefix="repo2ree-populated-") as marker:
                    _docker("cp", marker.name, f"{scratch}:/bundle-store/{_POPULATED_SENTINEL}")
                self._populated_volumes.add(bundle.volume_name)
            finally:
                _docker_silent("rm", "-f", "-v", scratch)

    def _docker_backend_args(self, ree_id: str) -> list[str]:
        if self._docker_mode == "dind":
            # No host docker.sock mount: the workbench runs its own in-container
            # daemon for per-REE isolation. /var/lib/docker is volume-backed so
            # the nested daemon uses overlay2, not vfs.
            return [
                "--privileged",
                "-e",
                "DOCKER_DRIVER=overlay2",
                # Upstream docker:dind entrypoints generate TLS material and
                # listen on tcp/2376 unless told not to; the bench daemon is
                # only ever reached over its local unix socket.
                "-e",
                "DOCKER_TLS_CERTDIR=",
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

    def is_running(self, ref: WorkbenchRef) -> bool:
        """Liveness gate for the control plane's availability check.

        A *confirmed* verdict (running, or a genuinely absent container) is
        returned as-is. An indeterminate probe — the daemon was momentarily
        unreachable or slow — is retried once and, if still unknown, leans
        *available*: declaring a healthy-looking bench dead here would fail the
        session's next action with a spurious "workbench unavailable", whereas a
        bench that really is gone surfaces a truthful error at the actual op.
        """
        handle = decode_reference(ref)
        with _docker_op("is_running") as op:
            for attempt in range(2):
                try:
                    return _container_running(handle.container_name)
                except ContainerStateUnknownError as exc:
                    if attempt == 0:
                        time.sleep(0.5)
                        continue
                    op.status = "unknown"
                    logger.warning(
                        "liveness probe indeterminate for %s (%s); assuming running",
                        handle.container_name,
                        exc,
                    )
                    return True
            return True  # unreachable: the loop always returns

    def exec_simple(self, ref: WorkbenchRef, argv: list[str], timeout: int = 60) -> None:
        handle = decode_reference(ref)
        with _docker_op("exec_simple"):
            self._exec(handle.container_name, [handle.exec_path, *argv], timeout, what=f"docker exec {argv[0]}")

    def cancel_run(self, ref: WorkbenchRef, run_id: str) -> None:
        self.exec_simple(ref, ["cancel-run", "--run-id", run_id], timeout=10)

    def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        handle = decode_reference(ref)
        with _docker_op("exec_query_stream"):
            yield from docker_cli.stream_exec(
                ["docker", "exec", handle.container_name, handle.exec_path, *argv], timeout, what=f"query {argv!r}"
            )

    @staticmethod
    def _exec(container_name: str, argv: list[str], timeout: int, what: str) -> bytes:
        """Run ``argv`` in the container and return its stdout bytes.

        Raises ``WorkbenchGoneError`` when the failure means the container is gone or
        stopping, ``RuntimeError`` for any other non-zero exit."""
        result = subprocess.run(
            ["docker", "exec", container_name, *argv],
            check=False,
            capture_output=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = docker_cli.tail_text(result.stderr)
            stdout = docker_cli.tail_text(result.stdout)
            detail = stderr or stdout or "(no output on stdout/stderr)"
            message = f"{what} failed (exit {result.returncode}): {detail}"
            if result.returncode in docker_cli.CONTAINER_GONE_EXIT_CODES or "No such container" in detail:
                raise WorkbenchGoneError(message)
            raise RuntimeError(message)
        return result.stdout

    def copy_in(self, ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        # ``source_path`` is a file on *our* host — the control plane streamed the
        # bytes here into a local temp file (see TransferStore), so there is no
        # shared-filesystem assumption with the control plane. ``docker cp``
        # resolves the destination path the same way it always has.
        handle = decode_reference(ref)
        with _docker_op("copy_in"):
            result = subprocess.run(
                ["docker", "cp", source_path, f"{handle.container_name}:{workbench_path}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(f"docker cp failed: {docker_cli.failure_detail(result.stderr, result.stdout)}")

    # ------------------------------------------------
    # Action dispatch (streaming)
    # ------------------------------------------------

    def exec_action(self, ref: WorkbenchRef, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[AgentFrame]:
        handle = decode_reference(ref)
        started_at = time.monotonic()
        status = "succeeded"
        recorded = False

        def record_once() -> None:
            nonlocal recorded
            if not recorded:
                _record_docker_operation("exec_action", started_at, status)
                recorded = True

        # The command is spawned from here, inside the agent's own request span,
        # so that span is its parent. Any traceparent the caller sent named a
        # span one hop further up — which would make the executor a *sibling* of
        # the request that ran it rather than its child, hiding the fact that
        # the agent is what invoked it and leaving the request's own time
        # unattributed. Injecting here keeps one propagation point, at the hop
        # that actually crosses into the container.
        forwarded = dict(env)
        if traceparent := current_traceparent():
            forwarded["TRACEPARENT"] = traceparent
        env_args: list[str] = []
        for key, value in forwarded.items():
            env_args += ["-e", f"{key}={value}"]

        try:
            proc = subprocess.Popen(
                [
                    "docker",
                    "exec",
                    "-i",
                    *env_args,
                    handle.container_name,
                    handle.exec_path,
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
        except Exception:
            status = "failed"
            record_once()
            raise

        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            status = "failed"
            record_once()
            raise RuntimeError("Popen pipes unavailable — stdin/stdout/stderr not opened")

        try:
            proc.stdin.write(cmd_json)
            proc.stdin.close()

            # Drain stdout concurrently while stderr streams below. Reading stdout
            # only after stderr closes would deadlock the moment the executor writes
            # more than the pipe buffer (~64 KiB) to stdout: the child blocks on the
            # full stdout pipe and never closes stderr.
            stdout_pipe = proc.stdout
            stdout_parts: list[str] = []
            stdout_reader = threading.Thread(target=lambda: stdout_parts.append(stdout_pipe.read()), daemon=True)
            stdout_reader.start()

            # The executor emits NDJSON log/span events on stderr; forward each as a
            # typed frame the moment it arrives (a hung/killed command still ships the
            # frames it emitted before stalling — the case a trace is most useful).
            for raw_line in proc.stderr:
                line = raw_line.rstrip()
                if not line:
                    continue
                frame = executor_frames.executor_line_to_frame(line)
                if frame is not None:
                    yield frame

            stdout_reader.join()
            stdout = "".join(stdout_parts).strip()
            proc.wait()

            if proc.returncode in docker_cli.CONTAINER_GONE_EXIT_CODES:
                status = "unavailable"
                yield UnavailableFrame(detail=f"docker exec exited {proc.returncode} — container gone or stopping")
                record_once()
                return

            result = executor_frames.parse_action_result(stdout, proc.returncode or 0)
            status = result.status
            yield ResultFrame(result=result)
        except Exception:
            if status == "succeeded":
                status = "failed"
            raise
        finally:
            record_once()


# ================================================
# Helpers
# ================================================


class _DockerOp:
    """Mutable status holder for an in-flight docker operation.

    The body may override ``status`` for an outcome the exception mapping can't
    infer (a result carrying its own status, or a probe that swallows an
    indeterminate result and returns a default)."""

    __slots__ = ("status",)

    def __init__(self) -> None:
        self.status = "succeeded"


@contextmanager
def _docker_op(operation: str) -> Generator[_DockerOp]:
    """Time a docker operation and record its metric exactly once, with the
    right terminal status on every exit path.

    Centralises the ``started_at``/``status``/``finally`` boilerplate that used
    to be hand-rolled at each call site — where forgetting to flip the status on
    a failure path (or hard-coding ``"succeeded"`` in the ``finally``) silently
    mislabelled errors as successes. Status defaults to ``"succeeded"``; a raised
    exception maps to ``"unavailable"`` (workbench gone), ``"unknown"`` (an
    indeterminate probe) or ``"failed"`` unless the body set one explicitly.
    ``Exception`` — not ``BaseException`` — so an abandoned generator
    (``GeneratorExit``) or cancellation is not recorded as a failure."""
    started_at = time.monotonic()
    op = _DockerOp()
    try:
        yield op
    except WorkbenchGoneError:
        op.status = "unavailable"
        raise
    except ContainerStateUnknownError:
        op.status = "unknown"
        raise
    except Exception:
        op.status = "failed"
        raise
    finally:
        _record_docker_operation(operation, started_at, op.status)


def _record_docker_operation(operation: str, started_at: float, status: str) -> None:
    attrs = command_metric_attrs(operation, status=status)
    _docker_operation_counter.add(1, attrs)
    _docker_operation_duration.record(time.monotonic() - started_at, attrs)
    if status == "unavailable":
        _workbench_gone_counter.add(1, command_metric_attrs(operation))
    # Docker CLI calls also become spans, so a slow provision breaks down into
    # its pulls/copies/runs in the trace. Higher-level operations (provision,
    # exec_action, …) are excluded — the agent.request span already covers
    # them, and a duplicate sibling would only clutter the waterfall.
    if operation.startswith("docker."):
        _emit_docker_span(operation, started_at, status)


def _emit_docker_span(operation: str, started_at: float, status: str) -> None:
    """Mint a completed span for a docker CLI call, with explicit timestamps.

    The helpers already time themselves for the duration metric, so instead of
    wrapping every call site (several are generators) the span is created
    retroactively at completion: started against the current context — nesting
    under the in-flight ``agent.request`` — and ended at the real boundaries.
    """
    end_ns = time.time_ns()
    start_ns = end_ns - int((time.monotonic() - started_at) * 1_000_000_000)
    span = tracer.start_span(operation, start_time=start_ns)
    record_command_status(span, status)
    span.end(end_time=end_ns)


def _docker(*args: str, timeout: int = 60) -> None:
    """Run a docker subcommand, raising on a non-zero exit."""
    _docker_out(*args, timeout=timeout)


def _docker_out(*args: str, timeout: int = 60) -> str:
    """Like :func:`_docker` but returns stripped stdout (e.g. a created container id)."""
    with _docker_op(f"docker.{args[0]}"):
        return docker_cli.docker_out(args, timeout)


def _image_present(image: str) -> bool:
    """True if the image already exists locally (no registry round-trip)."""
    with _docker_op("docker.image_inspect"):
        return docker_cli.image_present(image)


def _probe_bench(container_name: str, exec_path: str, image: str) -> Iterator[AgentFrame]:
    """Run ``repo2ree-exec doctor`` in the fresh bench and enforce the contract.

    Fail-fast is the point: a bench that can't run the executor at all, or
    whose ``/ree`` isn't writable, dies here with a specific message instead of
    hanging on its first build. Missing *capabilities* (docker substrate,
    handler tools) are reported as logs — whether a docker-less bench is
    acceptable is the control plane's call, not the agent's.
    """
    # The doctor itself polls up to ~15s for a still-starting dockerd; the exec
    # timeout just needs to comfortably exceed that.
    with _docker_op("docker.exec_doctor"):
        result = subprocess.run(
            ["docker", "exec", container_name, exec_path, "doctor"],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            detail = (
                docker_cli.tail_text(result.stderr.encode())
                or docker_cli.tail_text(result.stdout.encode())
                or "(no output)"
            )
            raise RuntimeError(f"bench from {image} failed the executor probe (exit {result.returncode}): {detail}")
        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"bench from {image} returned an unparseable doctor report: {exc}") from exc

        if not report.get("ok", False):
            raise RuntimeError(f"bench from {image} violates the workbench contract: /ree is not writable")

        docker_info = report.get("docker", {})
        if docker_info.get("available"):
            docker_summary = f"docker {docker_info.get('server_version', '?')}"
        else:
            docker_summary = f"no docker substrate ({docker_info.get('detail', 'unknown')})"
        tools = report.get("tools", {})
        present = sorted(name for name, path in tools.items() if path)
        missing = sorted(name for name, path in tools.items() if not path)
        yield LogFrame(
            stream="system",
            level="info",
            message=f"bench probe: {docker_summary}; tools present: {', '.join(present) or 'none'}"
            + (f"; missing: {', '.join(missing)}" if missing else ""),
        )
        if not docker_info.get("available"):
            yield LogFrame(
                stream="system",
                level="warn",
                message="bench has no reachable docker daemon — runtime builds and experiment runs will fail here",
            )


class ContainerStateUnknownError(RuntimeError):
    """`docker inspect` could not determine the container's state.

    Distinct from "container is not running": a timed-out or errored probe means
    the daemon was momentarily unreachable, not that the bench is gone. Callers
    must not treat this as a confirmed-down signal (which would fail a healthy
    session's next action with a spurious "workbench unavailable").
    """


def _container_running(container_name: str) -> bool:
    """True iff the container is *confirmed* running.

    Raises :class:`ContainerStateUnknownError` when the probe itself could not run —
    a timeout or a non-"not-found" docker error — so a transient daemon hiccup
    is never silently reported as "not running".
    """
    with _docker_op("docker.inspect"):
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerStateUnknownError(f"docker inspect timed out for {container_name}") from exc
        if result.returncode == 0:
            return result.stdout.strip() == "true"
        # A genuinely absent container is a confirmed "not running"; any other
        # failure (daemon unreachable, permission blip) is indeterminate.
        stderr = result.stderr.lower()
        if "no such object" in stderr or "no such container" in stderr:
            return False
        raise ContainerStateUnknownError(
            f"docker inspect failed for {container_name}: {docker_cli.failure_detail(result.stderr, result.stdout)}"
        )


def _image_has_nix(image: str) -> bool:
    """True if ``image`` carries its own /nix tree.

    Probed through a never-started scratch container: ``docker cp`` streams the
    path as a tar to stdout, so one readable byte proves existence — the
    process is killed immediately rather than streaming a whole nix store.
    The scratch command never runs, so it need not exist in the image.
    """
    scratch = _docker_out("create", image, "/repo2ree-noop")
    try:
        with _docker_op("docker.cp_probe_nix"):
            proc = subprocess.Popen(
                ["docker", "cp", f"{scratch}:/nix", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            if proc.stdout is None:
                raise RuntimeError("Popen stdout pipe unavailable")
            first_byte = proc.stdout.read(1)
            docker_cli.kill_process(proc)
            return bool(first_byte)
    finally:
        _docker_silent("rm", "-f", "-v", scratch)


def _container_path_exists(container_id: str, path: str) -> bool:
    """True if ``path`` exists inside the (possibly never-started) container."""
    with _docker_op("docker.cp_probe_path"):
        result = subprocess.run(
            ["docker", "cp", f"{container_id}:{path}", "-"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return result.returncode == 0


def _docker_stream_lines(*args: str, timeout: int = 600) -> Iterator[str]:
    """Run a docker command, yielding its output line-by-line as it arrives.

    Docker writes progress (pull layers, etc.) to stderr and only renders the
    animated bars when attached to a TTY — here it's a pipe, so we get plain
    line-by-line progress, which is what belongs in a log. Raises RuntimeError on
    a non-zero exit or a timeout so callers handle a hang like any other failure.
    """
    proc: subprocess.Popen[str] | None = None
    try:
        with _docker_op(f"docker.{args[0]}"):
            proc = subprocess.Popen(
                ["docker", *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout is None:
                raise RuntimeError("Popen stdout unavailable")
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
            if proc.returncode != 0:
                raise RuntimeError(f"docker {args[0]} failed (exit {proc.returncode})")
    finally:
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()


def _docker_silent(*args: str) -> None:
    """Like _docker but ignores failures (for cleanup paths)."""
    with _docker_op(f"docker.{args[0]}") as op:
        try:
            result = subprocess.run(["docker", *args], check=False, capture_output=True, timeout=30)
            if result.returncode != 0:
                op.status = "failed_ignored"
        except (subprocess.SubprocessError, OSError):
            op.status = "failed_ignored"


def _docker_remove(*args: str) -> None:
    """Idempotent but strict cleanup for acknowledged user deletion."""
    with _docker_op(f"docker.{args[0]}"):
        result = subprocess.run(["docker", *args], check=False, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return
        detail = docker_cli.failure_detail(result.stderr, result.stdout)
        if "No such container" in detail or "No such volume" in detail:
            return
        raise RuntimeError(f"docker {args[0]} failed: {detail}")
