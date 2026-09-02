"""Docker-backed workbench isolation: creating and destroying benches.

Owns volumes and containers, dind vs host-socket daemon modes, naming, the
pull-with-cache fallback, and the startup probe. It emits protocol frames for
streaming calls and never executes an REE command — that is the workbench
service's job, inside the bench this module starts.

Executor injection: when the provider ships a bundle (the
``REPO2REE_EXEC_BUNDLE`` dir — see nix/exec-bundle.nix), benches don't need
``repo2ree-exec`` baked into their image. The bundle's nix closure populates a
content-addressed volume once per host, mounts read-only at ``/nix/store`` in
every bench, and the executor's absolute path is recorded in the minted
``WorkbenchRef``. Images carrying their own ``/nix`` are left un-injected —
mounting over their store would shadow it — and must provide ``repo2ree-exec``
on PATH themselves.

The bench's main process is the image's own default command (docker:dind's
entrypoint starts ``dockerd`` only when dockerd is the command). A pause
command is strictly the rescue for images whose default exits immediately.
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
from urllib.parse import urlsplit, urlunsplit

from repo2ree_docker import cli as docker_cli
from repo2ree_docker.ops import (
    ContainerStateUnknownError,
    container_running,
    docker_op,
    run_docker,
    run_docker_out,
    run_docker_remove,
    run_docker_silent,
)
from repo2ree_docker.reference import (
    DockerWorkbenchHandle,
    decode_reference,
    encode_reference,
)
from repo2ree_protocol.frames import ErrorFrame, Frame, LogFrame, WorkbenchRef, WorkbenchRefFrame
from repo2ree_protocol.provider import DockerWorkbenchSpec
from repo2ree_provider_docker.injection import InjectionBundle, load_injection_bundle

__all__ = ["DockerIsolation"]

logger = logging.getLogger(__name__)

_WORKBENCH_DOCKER_MODES = frozenset({"dind", "host-socket"})
_HOST_DOCKER_SOCK_MOUNT = "/var/run/docker.sock:/var/run/docker.sock"
# The name every bench gets mapped to the host gateway, and the hosts that mean
# "this machine" to the provider but "this container" to the bench.
_HOST_GATEWAY_NAME = "host.docker.internal"
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
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


class DockerIsolation:
    """Creates, replaces, probes, and removes Docker-backed benches."""

    runtime_name = "docker"

    def __init__(
        self,
        docker_mode: str = "dind",
        exec_bundle_dir: str | None = None,
        tools_bundle_dir: str | None = None,
        *,
        workbench_api_ws_url: str = "ws://localhost:8000/workbench/connect",
        workbench_path: str | None = None,
        workbench_network: str = "",
    ):
        if docker_mode not in _WORKBENCH_DOCKER_MODES:
            modes = ", ".join(sorted(_WORKBENCH_DOCKER_MODES))
            raise ValueError(f"unknown workbench docker mode {docker_mode!r}; expected one of: {modes}")
        self._docker_mode = docker_mode
        self._workbench_network = workbench_network
        self._workbench_api_ws_url = _bench_reachable_url(workbench_api_ws_url, workbench_network)
        self._workbench_path = workbench_path or os.environ.get("REPO2REE_WORKBENCH_PATH")
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
        run_docker("volume", "create", *self._resource_label_args(), name)

    # ------------------------------------------------
    # Lifecycle (streaming)
    # ------------------------------------------------

    def provision(
        self,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: DockerWorkbenchSpec,
    ) -> Iterator[Frame]:
        container_name = self._container_name(ree_id)
        volume_name = self._volume_name(ree_id)
        image = spec.base_image
        with docker_op("provision") as op:
            try:
                self._create_workbench_volume(volume_name)
                if self._docker_mode == "dind":
                    self._create_workbench_volume(self._dind_volume_name(ree_id))
                exec_path = yield from self._run_workbench_container(
                    container_name,
                    ree_id,
                    volume_name,
                    image,
                    allocation_id=allocation_id,
                    workbench_id=workbench_id,
                    enrollment_token=enrollment_token,
                )
            except RuntimeError as exc:
                op.status = "failed"
                # Provision has not emitted a reference yet, so the supervisor
                # cannot compensate this partial creation. Reclaim every
                # deterministic resource here before returning the error frame.
                run_docker_silent("rm", "-f", "-v", container_name)
                run_docker_silent("volume", "rm", volume_name)
                if self._docker_mode == "dind":
                    run_docker_silent("volume", "rm", self._dind_volume_name(ree_id))
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

    def remove(self, ref: WorkbenchRef) -> None:
        handle = decode_reference(ref)
        with docker_op("remove"):
            # -v drops the anonymous volumes the image declared (docker:dind
            # declares /var/lib/docker and /certs, so every bench would leave
            # unreclaimable hex-named volumes behind). Named volumes — ours,
            # below — are never touched by it, which is why every `rm` here
            # carries it.
            run_docker_remove("rm", "-f", "-v", handle.container_name)
            run_docker_remove("volume", "rm", handle.volume_name)
            if self._docker_mode == "dind":
                run_docker_remove("volume", "rm", self._dind_volume_name(handle.ree_id))
            # The injected store volume is shared across benches and content-
            # addressed — never removed per REE.

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
        with docker_op("is_running") as op:
            for attempt in range(2):
                try:
                    return container_running(handle.container_name)
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

    def _run_workbench_container(
        self,
        container_name: str,
        ree_id: str,
        volume_name: str,
        image: str,
        *,
        allocation_id: str = "",
        workbench_id: str = "",
        enrollment_token: str = "",
    ) -> Generator[Frame, None, str]:
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
            # Source-run providers commonly hand the resident workbench a
            # host.docker.internal control-plane URL. Docker Engine on Linux
            # does not create that name unless explicitly requested; Docker
            # Desktop accepts the same host-gateway mapping.
            "--add-host",
            "host.docker.internal:host-gateway",
            *(["--network", self._workbench_network] if self._workbench_network else []),
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
            # The duration is not optional: the bundle's pause binary is busybox
            # `sleep`, which prints its usage and exits 1 when given no operand —
            # a pause command that pauses for nothing at all. `infinity` parses
            # (busybox's fancy sleep reads it as a float), and the image's own
            # `sleep` is the fallback when nothing was injected.
            pause = [bundle.pause_path, "infinity"] if bundle is not None else ["sleep", "infinity"]
            # A dind image in host-socket mode lands here by construction: its
            # default command is dockerd, which cannot start unprivileged, and
            # host-socket deliberately withholds --privileged. The substrate it
            # needs is the mounted host socket, not that daemon, so a bench held
            # open by the pause command is the *correct* bench — but say so, since
            # in dind mode the same fallback means the nested daemon died and the
            # probe below is about to report a bench with no docker substrate.
            message = f"image {image} default command did not stay running; holding the bench open with {pause[0]}"
            logger.warning(message)
            yield LogFrame(stream="system", level="warn", message=message)
            if not self._start_bench(container_name, run_args, image, command=pause):
                raise RuntimeError(
                    f"bench container from {image} would not stay running "
                    "(its default command and the pause command both exited)"
                )
        yield from _probe_bench(container_name, exec_path, image)
        if allocation_id:
            self._start_resident_workbench(
                container_name,
                allocation_id=allocation_id,
                workbench_id=workbench_id,
                enrollment_token=enrollment_token,
                exec_path=exec_path,
                tool_env=bundle.tool_env if bundle is not None else {},
            )
        return exec_path

    def _start_resident_workbench(
        self,
        container_name: str,
        *,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        exec_path: str,
        tool_env: dict[str, str],
    ) -> None:
        environment = {
            "WORKBENCH_API_WS_URL": self._workbench_api_ws_url,
            "WORKBENCH_ID": workbench_id,
            "WORKBENCH_MODE": "managed",
            "WORKBENCH_ALLOCATION_ID": allocation_id,
            "WORKBENCH_AUTH_TOKEN": enrollment_token,
            "WORKBENCH_ROOT": "/ree",
            "WORKBENCH_SUBSTRATE": "docker-nested" if self._docker_mode == "dind" else "docker-host-socket",
            "REPO2REE_EXEC_PATH": exec_path,
            **tool_env,
        }
        env_args = [part for key, value in sorted(environment.items()) for part in ("-e", f"{key}={value}")]
        workbench_path = (
            self._workbench_path
            or (self._bundle.workbench_path if self._bundle is not None else None)
            or "repo2ree-workbench"
        )
        run_docker("exec", "-d", *env_args, container_name, workbench_path, timeout=120)

    @staticmethod
    def _start_bench(container_name: str, run_args: list[str], image: str, command: list[str]) -> bool:
        """Start the bench and report whether it stayed up past the grace window.

        The restart policy is applied only *after* the container proves viable —
        starting with ``--restart unless-stopped`` would turn an exits-immediately
        default command into a silent crash loop instead of a falsifiable check.
        A failed attempt is removed so the retry can reuse the name.
        """
        run_docker("run", "-d", *run_args, image, *command, timeout=120)
        time.sleep(_STARTUP_GRACE_SECONDS)
        # The grace check is a falsifiable "did it stay up"; an indeterminate
        # probe is not proof it did, so treat it as this attempt not being
        # viable (fall back / retry) rather than promoting an unconfirmed bench.
        try:
            stayed_up = container_running(container_name)
        except ContainerStateUnknownError:
            stayed_up = False
        if not stayed_up:
            run_docker_silent("rm", "-f", "-v", container_name)
            return False
        run_docker("update", "--restart", "unless-stopped", container_name)
        return True

    def _ensure_store_volume(self, image: str, bundle: InjectionBundle) -> Iterator[Frame]:
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
            run_docker("volume", "create", bundle.volume_name)
            scratch = run_docker_out("create", "-v", f"{bundle.volume_name}:/bundle-store", image, "/repo2ree-noop")
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
                    run_docker("cp", source, f"{scratch}:/bundle-store", timeout=600)
                with tempfile.NamedTemporaryFile(prefix="repo2ree-populated-") as marker:
                    run_docker("cp", marker.name, f"{scratch}:/bundle-store/{_POPULATED_SENTINEL}")
                self._populated_volumes.add(bundle.volume_name)
            finally:
                run_docker_silent("rm", "-f", "-v", scratch)

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


# ================================================
# Helpers
# ================================================


def _bench_reachable_url(url: str, workbench_network: str) -> str:
    """Rewrite a loopback control-plane URL to one the bench can actually dial.

    This URL is not the provider's to use — it is handed to the resident
    workbench *inside* a container, where loopback is the container itself. A
    provider run from source against a control plane on its own machine
    otherwise points every bench at its own empty port 8000 and the allocation
    dies on the connect timeout, sixty seconds away from any clue why.

    ``--add-host host.docker.internal:host-gateway`` is already on every bench
    for exactly this, so the name resolves on Docker Engine as well as Desktop.
    A bench sharing the host's network namespace is the one case where loopback
    is already correct, and is left alone.
    """
    if workbench_network == "host":
        return url
    parsed = urlsplit(url)
    if parsed.hostname not in _LOOPBACK_HOSTS:
        return url
    authority = _HOST_GATEWAY_NAME if parsed.port is None else f"{_HOST_GATEWAY_NAME}:{parsed.port}"
    if parsed.username:
        credentials = parsed.username if parsed.password is None else f"{parsed.username}:{parsed.password}"
        authority = f"{credentials}@{authority}"
    rewritten = urlunsplit(parsed._replace(netloc=authority))
    logger.info("rewrote bench control-plane URL %s to %s so benches can reach it", url, rewritten)
    return rewritten


def _image_present(image: str) -> bool:
    """True if the image already exists locally (no registry round-trip)."""
    with docker_op("docker.image_inspect"):
        return docker_cli.image_present(image)


def _probe_bench(container_name: str, exec_path: str, image: str) -> Iterator[Frame]:
    """Run ``repo2ree-exec doctor`` in the fresh bench and enforce the contract.

    Fail-fast is the point: a bench that can't run the executor at all, or
    whose ``/ree`` isn't writable, dies here with a specific message instead of
    hanging on its first build. Missing *capabilities* (docker substrate,
    handler tools) are reported as logs — whether a docker-less bench is
    acceptable is the control plane's call, not the provider's.
    """
    # The doctor itself polls up to ~15s for a still-starting dockerd; the exec
    # timeout just needs to comfortably exceed that.
    with docker_op("docker.exec_doctor"):
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


def _image_has_nix(image: str) -> bool:
    """True if ``image`` carries its own /nix tree.

    Probed through a never-started scratch container: ``docker cp`` streams the
    path as a tar to stdout, so one readable byte proves existence — the
    process is killed immediately rather than streaming a whole nix store.
    The scratch command never runs, so it need not exist in the image.
    """
    scratch = run_docker_out("create", image, "/repo2ree-noop")
    try:
        with docker_op("docker.cp_probe_nix"):
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
        run_docker_silent("rm", "-f", "-v", scratch)


def _container_path_exists(container_id: str, path: str) -> bool:
    """True if ``path`` exists inside the (possibly never-started) container."""
    with docker_op("docker.cp_probe_path"):
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
        with docker_op(f"docker.{args[0]}"):
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
