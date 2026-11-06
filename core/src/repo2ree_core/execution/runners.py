"""Where an author's script runs: on the workbench's host, or in a fresh container from the REE's image.

The workbench chooses (``REPO2REE_SCRIPT_RUNNER``, JSON) and the executor reads the choice
once. A container runner mounts only the workspace, at the same absolute path (a packed venv
keeps the path it was built at), so a script never reaches the REE's history or receipts. It
reports what it ran in, which the receipts of the step record.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal, Protocol

from repo2ree_core.execution.environment import host_fingerprint, observe_environment
from repo2ree_core.execution.process import (
    CancelCheck,
    StepOutcome,
    StreamingProcessResult,
    format_argv,
    run_streaming_process,
)
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionStatus
from repo2ree_ree.digest import Digest
from repo2ree_ree.environment import EnvironmentDefinition, EnvironmentObservation
from repo2ree_ree.paths import resolve_within
from repo2ree_telemetry.bootstrap import get_tracer
from repo2ree_telemetry.spans import ScriptSpanAttrs, record_command_status, record_span_facts

tracer = get_tracer(__name__)

RUNNER_VARIABLE = "REPO2REE_SCRIPT_RUNNER"
# The label naming whose job a container is: the store its workbench serves.
JOB_OWNER_LABEL = "repo2ree.job-owner"
# The label naming the execution a job belongs to, so a restarted workbench keeps the ones it adopts.
JOB_EXECUTION_LABEL = "repo2ree.job-execution"
EXECUTION_VARIABLE = "REPO2REE_EXECUTION"
# Where a container finds the host engine's socket, when a script may reach it.
_ENGINE_SOCKET = "/var/run/docker.sock"


class ScriptRunner(Protocol):
    def run(
        self, workspace: Path, argv: list[str], *, log: LogSink, is_canceled: CancelCheck
    ) -> StreamingProcessResult: ...

    def observe(self, declared: EnvironmentDefinition | None) -> EnvironmentObservation: ...


class LocalScriptRunner:
    """The script runs on the workbench's own host, from the workspace."""

    def run(
        self, workspace: Path, argv: list[str], *, log: LogSink, is_canceled: CancelCheck
    ) -> StreamingProcessResult:
        return run_streaming_process(argv, log=log, cwd=workspace, is_canceled=is_canceled)

    def observe(self, declared: EnvironmentDefinition | None) -> EnvironmentObservation:
        return observe_environment(declared)


@dataclass
class ContainerScriptRunner:
    """The script runs in a fresh container from ``image``, with only the workspace mounted."""

    engine: str
    image: str
    script_engine: Literal["none", "socket"] = "none"
    # Where the engine finds this workbench's files, when it does not see them where the workbench
    # does (a workbench in a container beside the host's engine): (local prefix, engine prefix).
    engine_path: tuple[str, str] | None = None
    # Who the job belongs to (its store), so what a killed workbench leaves running can be removed.
    owner: str = ""
    _digest: str | None = None

    def run(
        self, workspace: Path, argv: list[str], *, log: LogSink, is_canceled: CancelCheck
    ) -> StreamingProcessResult:
        image = self._resolved(log)
        name = f"repo2ree-job-{uuid.uuid4().hex[:12]}"
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
        labels = ["--label", f"{JOB_OWNER_LABEL}={self.owner}"] if self.owner else []
        if execution := os.environ.get(EXECUTION_VARIABLE, "").strip():
            labels += ["--label", f"{JOB_EXECUTION_LABEL}={execution}"]
        if resource_owner := os.environ.get("REPO2REE_RESOURCE_OWNER", "").strip():
            labels += ["--label", f"repo2ree.resource-owner={resource_owner}"]
        command = [
            *(self.engine, "run", "--rm", "--init", "--name", name, *labels, *mounts),
            *("-w", workdir, image, *argv),
        ]
        try:
            return run_streaming_process(command, log=log, is_canceled=is_canceled)
        finally:
            # A canceled run stops the engine's client, not always the container it started.
            subprocess.run([self.engine, "rm", "-f", name], check=False, capture_output=True, timeout=60)
            self._hand_back(workspace, image, mounts, log)

    def _hand_back(self, workspace: Path, image: str, mounts: list[str], log: LogSink) -> None:
        """Give what the script wrote back to the workbench's user.

        The script runs as its image's user (often root, which an environment may need), so on a
        host whose engine keeps file ownership what it wrote would be root's, and unreadable here.
        """
        user = f"{os.getuid()}:{os.getgid()}"
        if user == "0:0":
            return
        handed = subprocess.run(
            [self.engine, "run", "--rm", "--user", "0:0", *mounts, image, "chown", "-R", user, str(workspace)],
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if handed.returncode != 0:
            log("system", "warn", f"could not give the workspace back to {user}: {handed.stderr.strip()[:200]}")

    def _engine_side(self, path: Path) -> str:
        """``path`` as the engine sees it; the job still sees it at ``path``."""
        if self.engine_path is None:
            return str(path)
        local, engine = self.engine_path
        relative = path.relative_to(local) if path.is_relative_to(local) else None
        return str(Path(engine) / relative) if relative is not None else str(path)

    def observe(self, declared: EnvironmentDefinition | None) -> EnvironmentObservation:
        return EnvironmentObservation(
            declared=declared,
            backend="container",
            image_digest=Digest(self._digest) if self._digest else None,
            host=host_fingerprint(container_engine=self.engine),
            script_engine=self.script_engine,
        )

    def _resolved(self, log: LogSink) -> str:
        """The image's id, pulled first if this host does not have it; its digest is remembered.

        The script runs from the id, so a tag that moves meanwhile changes nothing it runs in.
        """
        resolved = _inspect(self.engine, self.image)
        if resolved is None:
            log("system", "info", f"pulling {self.image}")
            subprocess.run([self.engine, "pull", self.image], check=True, capture_output=True, timeout=1800)
            resolved = _inspect(self.engine, self.image)
        if resolved is None:
            raise RuntimeError(f"{self.image} is not an image {self.engine} can run")
        image_id, self._digest = resolved
        log("system", "info", f"running in {self.image} ({self._digest})")
        return image_id


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
    digest = repo_digest.rpartition("@")[2] or image_id
    return (image_id, digest) if image_id.startswith("sha256:") and digest.startswith("sha256:") else None


@cache
def current_runner() -> ScriptRunner:
    """The runner this executor process was told to use; on the host when told nothing."""
    stated = os.environ.get(RUNNER_VARIABLE, "").strip()
    if not stated:
        return LocalScriptRunner()
    choice = json.loads(stated)
    if refused := choice.get("refused"):
        raise RuntimeError(refused)
    if choice.get("backend") != "container":
        return LocalScriptRunner()
    image = choice.get("image") or ""
    if not image:
        raise RuntimeError("this workbench runs scripts in a container, and the REE declares no image to run them in")
    mapped = choice.get("engine_path")
    return ContainerScriptRunner(
        engine=choice.get("engine") or "docker",
        image=image,
        script_engine=choice.get("script_engine") or "none",
        engine_path=(mapped["local"], mapped["engine"]) if mapped else None,
        owner=choice.get("owner") or "",
    )


def run_workspace_script(
    workspace: Path,
    script_rel: str,
    *,
    log: LogSink,
    is_canceled: CancelCheck = lambda: False,
) -> StepOutcome:
    """Run a workspace-relative script under ``sh`` from the workspace root.

    The single execution path shared by the lifecycle runner
    (``experiment/run.py``) and the build/activation handlers: the script runs
    where the workbench's runner puts it: on its host, or in a fresh container
    from the REE's image. Running from the workspace root lets authors reference
    project files by their workspace-relative paths regardless of where REE keeps
    its own scripts; wrapper scripts are POSIX ``sh`` while project scripts that
    need bash or their own directory (e.g. ``docker build .``) invoke it
    explicitly. Scripts that resolve outside the workspace are rejected.
    """
    workspace = workspace.resolve()
    with tracer.start_as_current_span("script.run") as span:
        ScriptSpanAttrs(path=script_rel).apply(span)
        script_abs = resolve_within(workspace, script_rel)
        if script_abs is None:
            log("system", "error", f"script escapes workspace: {script_rel}")
            record_span_facts(span, {"script.error": "escapes workspace"})
            return StepOutcome("failed", 1)
        if not script_abs.is_file():
            log("system", "error", f"script not found: {script_rel}")
            record_span_facts(span, {"script.error": "not found"})
            return StepOutcome("failed", 1)

        cmd = ["sh", script_rel]
        log("system", "info", f"$ {format_argv(cmd)}")

        result = current_runner().run(workspace, cmd, log=log, is_canceled=is_canceled)

        if result.canceled or is_canceled():
            status: ActionStatus = "canceled"
        else:
            status = "succeeded" if result.returncode == 0 else "failed"
        record_command_status(span, status)
        return StepOutcome(status, result.returncode, result.stdout, result.stderr)
