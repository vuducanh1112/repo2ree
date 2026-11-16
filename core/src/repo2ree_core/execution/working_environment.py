"""Entering an REE's working environment: the OCI image its scripts run in, or the machine itself.

The REE declares the image (``definition.working_environment``); the machine says how it enters one: which engine,
whether a script may reach that engine, where the engine finds this machine's files, and whose jobs its containers
are. ``ree`` reads the machine from its environment (``Machine.from_environment``), so it enters the declared
image whoever runs it, a person or a workbench.

An entry is an argv prefix. A step's command is composed outside in: the REE's launch (a scheduler), the recorder
of where the launch put it, the entry into the working environment, the activation, the script. So a scheduler
places a job, and the job enters the image on the node it landed on.
"""

from __future__ import annotations

import functools
import hashlib
import os
import platform
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from repo2ree_core.execution.process import CancelCheck, StreamingProcessResult, run_streaming_process
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.machine import EngineName, MachineFacts, ScriptEngineAccess
from repo2ree_ree.digest import Digest
from repo2ree_ree.working_environment import (
    HostFingerprint,
    ImageSource,
    WorkingEnvironment,
    WorkingEnvironmentObservation,
)

SCRIPT_ENGINE_VARIABLE = "REPO2REE_SCRIPT_ENGINE"
JOB_OWNER_VARIABLE = "REPO2REE_JOB_OWNER"
# The label naming whose job a container is: the store its workbench serves.
JOB_OWNER_LABEL = "repo2ree.job-owner"
# The label naming the execution a job belongs to, so a restarted workbench keeps the ones it adopts.
JOB_EXECUTION_LABEL = "repo2ree.job-execution"
EXECUTION_VARIABLE = "REPO2REE_EXECUTION"
# The engines looked for on PATH, in order.
_DETECTED: tuple[EngineName, ...] = ("docker", "podman", "apptainer")
# The engines that can save an image into a bundle.
_SAVING: tuple[Literal["docker", "podman"], ...] = ("docker", "podman")
# Where a container finds the host engine's socket, when a script may reach it.
_ENGINE_SOCKET = "/var/run/docker.sock"
_OS_RELEASE = Path("/etc/os-release")


class WorkingEnvironmentUnavailableError(RuntimeError):
    """The working environment cannot be entered here, and why."""


@dataclass(frozen=True)
class ProbeResult:
    """What a probe printed where the REE's scripts run; ``returncode`` None when it ran out of time."""

    runner: Literal["host", "container"]
    image: str | None
    returncode: int | None
    stdout: str
    stderr: str


class Entry(Protocol):
    """How a step's scripts enter the working environment."""

    def prepare(self, log: LogSink) -> None:
        """Make the environment enterable (pull or load its image); raises when it cannot be."""
        ...

    def command(self, workspace: Path, argv: list[str]) -> list[str]:
        """``argv`` run inside the environment, from ``workspace``."""
        ...

    def finish(self, workspace: Path, log: LogSink) -> None:
        """Remove what entering left behind, and give the workspace back to this user."""
        ...

    def observe(self) -> WorkingEnvironmentObservation:
        """What the step's scripts ran in."""
        ...


def host_fingerprint(container_engine: str = "") -> HostFingerprint:
    return HostFingerprint(
        os=_os_name(),
        arch=platform.machine() or "unknown",
        kernel=platform.release(),
        container_engine=container_engine,
    )


def _os_name() -> str:
    try:
        for line in _OS_RELEASE.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.partition("=")[2].strip().strip('"') or platform.system()
    except OSError:
        pass
    return platform.system() or "unknown"


@dataclass(frozen=True)
class HostEntry:
    """No environment to enter: the scripts run on the machine that runs the step."""

    def prepare(self, log: LogSink) -> None:
        return None

    def command(self, workspace: Path, argv: list[str]) -> list[str]:
        return list(argv)

    def finish(self, workspace: Path, log: LogSink) -> None:
        return None

    def observe(self) -> WorkingEnvironmentObservation:
        return WorkingEnvironmentObservation(declared=None, backend="host", host=host_fingerprint())


@dataclass(frozen=True)
class RefusedEntry:
    """The working environment cannot be entered on this machine; every use says why."""

    reason: str

    def prepare(self, log: LogSink) -> None:
        raise WorkingEnvironmentUnavailableError(self.reason)

    def command(self, workspace: Path, argv: list[str]) -> list[str]:
        raise WorkingEnvironmentUnavailableError(self.reason)

    def finish(self, workspace: Path, log: LogSink) -> None:
        return None

    def observe(self) -> WorkingEnvironmentObservation:
        raise WorkingEnvironmentUnavailableError(self.reason)


def bundled_image_name(declared: WorkingEnvironment) -> str:
    """The name a sealed bundle's image carries, so a review that loads it finds it again."""
    return f"repo2ree/working-environment:{hashlib.sha256(declared.oci.encode()).hexdigest()[:16]}"


@dataclass
class ContainerEntry:
    """Each script runs in a fresh container from the image, with only the workspace mounted, at its own path.

    The image is the engine's when it has it or can pull it; otherwise the REE's bundle's, when it carries one.
    """

    engine: Literal["docker", "podman"]
    declared: WorkingEnvironment
    bundled: Path | None = None
    script_engine: ScriptEngineAccess = "none"
    owner: str = ""
    _image: str | None = None
    _digest: str | None = None
    _source: ImageSource | None = None
    _names: list[str] = field(default_factory=list)
    _mounts: list[str] = field(default_factory=list)

    def prepare(self, log: LogSink) -> None:
        if self._image is not None:
            return
        found = _inspect(self.engine, self.declared.oci)
        source: ImageSource = "engine"
        if found is None:
            log("system", "info", f"pulling {self.declared.oci}")
            pulled = subprocess.run(
                [self.engine, "pull", self.declared.oci], check=False, capture_output=True, text=True, timeout=1800
            )
            found = _inspect(self.engine, self.declared.oci) if pulled.returncode == 0 else None
            if found is None and self.bundled is not None and self.bundled.is_file():
                log("system", "info", f"{self.declared.oci} cannot be pulled; loading the image the REE carries")
                found, source = self._load(self.bundled, log), "bundle"
            if found is None:
                why = (pulled.stderr.strip().splitlines() or ["no such image"])[-1]
                raise WorkingEnvironmentUnavailableError(
                    f"{self.declared.oci} is not an image {self.engine} can run: {why}"
                )
        self._image, self._digest, self._source = found[0], found[1], source
        log("system", "info", f"running in {self.declared.oci} ({self._digest})")

    def _load(self, bundled: Path, log: LogSink) -> tuple[str, str] | None:
        loaded = subprocess.run(
            [self.engine, "load", "-i", str(bundled)], check=False, capture_output=True, text=True, timeout=1800
        )
        if loaded.returncode != 0:
            log("system", "warn", f"could not load the REE's image: {loaded.stderr.strip()[:200]}")
            return None
        return _inspect(self.engine, bundled_image_name(self.declared))

    @property
    def image_id(self) -> str:
        """The id of the image the scripts run from, once prepared."""
        if self._image is None:
            raise WorkingEnvironmentUnavailableError("the working environment was entered before it was prepared")
        return self._image

    def command(self, workspace: Path, argv: list[str]) -> list[str]:
        if self._image is None:
            raise WorkingEnvironmentUnavailableError("the working environment was entered before it was prepared")
        name = f"repo2ree-job-{uuid.uuid4().hex[:12]}"
        self._names.append(name)
        engine_side = self._engine_side(workspace)
        mounts = ["-v", f"{engine_side}:{workspace}"]
        workdir = str(workspace)
        if self.script_engine == "socket":
            mounts += ["-v", f"{_ENGINE_SOCKET}:{_ENGINE_SOCKET}", "-e", f"DOCKER_HOST=unix://{_ENGINE_SOCKET}"]
            if engine_side != str(workspace):
                # A path the script hands the engine ("docker run -v $(pwd):…") must be one the engine
                # knows: the script also sees its workspace where the engine does, and starts there.
                mounts += ["-v", f"{engine_side}:{engine_side}"]
                workdir = engine_side
        self._mounts = mounts
        labels = ["--label", f"{JOB_OWNER_LABEL}={self.owner}"] if self.owner else []
        if execution := os.environ.get(EXECUTION_VARIABLE, "").strip():
            labels += ["--label", f"{JOB_EXECUTION_LABEL}={execution}"]
        if resource_owner := os.environ.get("REPO2REE_RESOURCE_OWNER", "").strip():
            labels += ["--label", f"repo2ree.resource-owner={resource_owner}"]
        return [
            *(self.engine, "run", "--rm", "--init", "--name", name, *labels, *mounts),
            *("-w", workdir, self._image, *argv),
        ]

    def finish(self, workspace: Path, log: LogSink) -> None:
        # A canceled run stops the engine's client, not always the container it started.
        for name in self._names:
            subprocess.run([self.engine, "rm", "-f", name], check=False, capture_output=True, timeout=60)
        self._names.clear()
        if self._image is not None and self._mounts:
            self._hand_back(workspace, log)

    def _hand_back(self, workspace: Path, log: LogSink) -> None:
        """Give what the script wrote back to this machine's user.

        The script runs as its image's user (often root, which an environment may need), so on a host whose
        engine keeps file ownership what it wrote would be root's, and unreadable here. The workspace itself names
        the owner, as the container sees it: a rootless engine maps this user to the container's root.
        """
        user = f"{os.getuid()}:{os.getgid()}"
        if user == "0:0" or self._image is None:
            return
        handed = subprocess.run(
            [
                *(self.engine, "run", "--rm", "--user", "0:0", *self._mounts, self._image),
                *("sh", "-c", 'chown -R "$(stat -c %u:%g "$0")" "$0"', str(workspace)),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if handed.returncode != 0:
            log("system", "warn", f"could not give the workspace back to {user}: {handed.stderr.strip()[:200]}")

    def _engine_side(self, path: Path) -> str:
        """``path`` as the engine sees it; the job still sees it at ``path``.

        They differ when this process runs in a container beside the engine (a workbench in a container, a dev
        container): the engine knows the workspace by the source of the mount it reaches this container through.
        """
        for local, source in _own_mounts(self.engine):
            if path == Path(local) or path.is_relative_to(local):
                return str(Path(source) / path.relative_to(local))
        return str(path)

    def observe(self) -> WorkingEnvironmentObservation:
        return WorkingEnvironmentObservation(
            declared=self.declared,
            backend="container",
            image_digest=Digest(self._digest) if self._digest else None,
            image_source=self._source,
            host=host_fingerprint(container_engine=self.engine),
            script_engine=self.script_engine,
        )


@dataclass
class ApptainerEntry:
    """Each script runs in the image through Apptainer, on whichever node runs it: a cluster's way to a container.

    Apptainer runs an image by its digest, so the REE pins it, and the step records that pin; a bundle that carries
    the image runs from it, which needs no registry on the node.
    """

    declared: WorkingEnvironment
    bundled: Path | None = None
    _source: ImageSource | None = None

    def prepare(self, log: LogSink) -> None:
        self._source = "bundle" if self.bundled is not None and self.bundled.is_file() else "engine"
        log("system", "info", f"running in {self.declared.oci} through apptainer, from the {self._source}")

    def command(self, workspace: Path, argv: list[str]) -> list[str]:
        image = f"docker-archive:{self.bundled}" if self._source == "bundle" else f"docker://{self.declared.oci}"
        return ["apptainer", "exec", "--bind", f"{workspace}:{workspace}", "--pwd", str(workspace), image, *argv]

    def finish(self, workspace: Path, log: LogSink) -> None:
        return None

    def observe(self) -> WorkingEnvironmentObservation:
        return WorkingEnvironmentObservation(
            declared=self.declared,
            backend="container",
            image_digest=Digest(self.declared.digest or ""),
            image_source=self._source,
            host=host_fingerprint(container_engine="apptainer"),
        )


@dataclass(frozen=True)
class Machine:
    """How this machine enters a working environment: with the first engine it has.

    The REE says what its scripts run in, and ``ree`` does that; it refuses only what this machine cannot do.
    """

    # Whether a script in a container may reach the engine, for the builds that still run it themselves.
    script_engine: ScriptEngineAccess = "none"
    owner: str = ""

    @classmethod
    def from_environment(cls) -> Machine:
        script_engine = os.environ.get(SCRIPT_ENGINE_VARIABLE, "").strip() or "none"
        if script_engine not in ("none", "socket"):
            raise ValueError(f"{SCRIPT_ENGINE_VARIABLE} is none or socket, not {script_engine!r}")
        return cls(
            script_engine=script_engine,  # type: ignore[arg-type]
            owner=os.environ.get(JOB_OWNER_VARIABLE, "").strip(),
        )

    def enter(self, declared: WorkingEnvironment | None, *, bundled: Path | None = None) -> Entry:
        """How a step enters ``declared`` here; ``bundled`` is the image the REE carries, when it carries one."""
        if declared is None:
            return HostEntry()
        engine = detected_engine()
        if engine == "apptainer":
            if not declared.pinned:
                return RefusedEntry(
                    f"apptainer runs an image by its digest: pin the working environment ({declared.oci}@sha256:…)"
                )
            return ApptainerEntry(declared, bundled)
        if engine == "docker" or engine == "podman":
            return ContainerEntry(engine, declared, bundled=bundled, script_engine=self.script_engine, owner=self.owner)
        return RefusedEntry(f"this machine has no container engine to run the REE's scripts in {declared.oci}")

    def facts(self) -> MachineFacts:
        """How this machine runs an REE's scripts, and what it offers them."""
        return MachineFacts(
            arch=platform.machine(), engine=detected_engine(), script_engine=self.script_engine, gpus=_gpu_count()
        )

    def engine_for_saving(self) -> Literal["docker", "podman"] | None:
        """The engine that can save an image into a bundle here; None when there is none."""
        return next((name for name in _SAVING if shutil.which(name)), None)


HOST_MACHINE = Machine()


def detected_engine() -> EngineName:
    """The engine this machine enters an image with: the first of docker, podman and apptainer on its PATH."""
    return next((name for name in _DETECTED if shutil.which(name)), "none")


def save_image(machine: Machine, declared: WorkingEnvironment, target: Path, log: LogSink) -> None:
    """Save the image ``declared`` names into ``target``, under the name a review loads it by."""
    engine = machine.engine_for_saving()
    if engine is None:
        raise WorkingEnvironmentUnavailableError("including the working environment needs docker or podman here")
    entry = ContainerEntry(engine, declared)
    entry.prepare(log)
    name = bundled_image_name(declared)
    for command in ([engine, "tag", entry.image_id, name], [engine, "save", "-o", str(target), name]):
        done = subprocess.run(command, check=False, capture_output=True, text=True, timeout=3600)
        if done.returncode != 0:
            raise WorkingEnvironmentUnavailableError(f"{' '.join(command[:2])} failed: {done.stderr.strip()[:300]}")


def probe(entry: Entry, workspace: Path, argv: list[str], *, seconds: float) -> ProbeResult:
    """Run ``argv`` where a script runs, as a script would, for at most ``seconds``, keeping what it prints out of
    the step's logs. A probe reads and writes nothing in the workspace."""
    entry.prepare(_quiet)
    observed = entry.observe()
    try:
        command = entry.command(workspace, argv)
        try:
            done = subprocess.run(command, cwd=workspace, check=False, capture_output=True, text=True, timeout=seconds)
            returncode, stdout, stderr = done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired as expired:
            returncode, stdout, stderr = None, _text(expired.stdout), _text(expired.stderr)
    finally:
        entry.finish(workspace, _quiet)
    image = observed.declared.oci if observed.declared else None
    return ProbeResult(runner=observed.backend, image=image, returncode=returncode, stdout=stdout, stderr=stderr)


def run_in(
    entry: Entry, workspace: Path, command: list[str], *, log: LogSink, is_canceled: CancelCheck
) -> StreamingProcessResult:
    """Run an already composed command from ``workspace``, then clean up after the entry."""
    try:
        return run_streaming_process(command, log=log, cwd=workspace, is_canceled=is_canceled)
    finally:
        entry.finish(workspace, log)


def _text(output: str | bytes | None) -> str:
    return output.decode(errors="replace") if isinstance(output, bytes) else output or ""


def _quiet(_stream: str, _level: str, _message: str) -> None:
    return None


def _inspect(engine: str, image: str) -> tuple[str, str] | None:
    """A local image's id, and its content digest: its registry digest, or its id when it has none."""
    inspected = subprocess.run(
        [engine, "image", "inspect", "--format", "{{.Id}} {{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}", image],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if inspected.returncode != 0:
        return None
    image_id, _, repo_digest = inspected.stdout.strip().partition(" ")
    # Docker prints the id with its algorithm, and Podman without.
    if image_id and ":" not in image_id:
        image_id = f"sha256:{image_id}"
    digest = repo_digest.rpartition("@")[2] or image_id
    return (image_id, digest) if image_id.startswith("sha256:") and digest.startswith("sha256:") else None


def _own_mounts(engine: str) -> tuple[tuple[str, str], ...]:
    """Where this process's container mounts what, as ``(destination, engine-side source)``; none outside one."""
    if not (Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()):
        return ()
    # Asked once per engine binary: the answer is the engine's, so another binary of the same name asks again.
    return _mounts_seen_by(shutil.which(engine) or engine)


@functools.cache
def _mounts_seen_by(engine: str) -> tuple[tuple[str, str], ...]:
    container = _own_container_id() or os.environ.get("HOSTNAME", "")
    if not container:
        return ()
    try:
        inspected = subprocess.run(
            [engine, "inspect", container, "--format", "{{range .Mounts}}{{.Destination}}={{.Source}};{{end}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if inspected.returncode != 0:
        return ()
    pairs = (mount.partition("=") for mount in inspected.stdout.strip().split(";") if mount)
    # The deepest mount first, so a path under a nested mount maps through that one.
    return tuple(sorted(((local, source) for local, _, source in pairs), key=lambda pair: -len(pair[0])))


def _own_container_id() -> str | None:
    """This container's id, as the engine names it, from where its hostname file is mounted from."""
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        found = re.search(r"/containers/([0-9a-f]{64})/", line)
        if found:
            return found.group(1)
    return None


def _gpu_count() -> int:
    """NVIDIA GPUs, as ``nvidia-smi -L`` lists them; none where it is absent or does not answer."""
    if shutil.which("nvidia-smi") is None:
        return 0
    try:
        listed = subprocess.run(["nvidia-smi", "-L"], check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return 0
    return sum(1 for line in listed.stdout.splitlines() if line.startswith("GPU ")) if listed.returncode == 0 else 0
