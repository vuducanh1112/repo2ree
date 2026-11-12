"""Native executor supervision inside one supplied workbench environment.

A workbench serves a store: it keeps one directory per REE beneath its root and runs each command
against the directory of the REE the request names.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from repo2ree_protocol.build import BuildInfo
from repo2ree_telemetry.spans import current_traceparent

# An REE id names a directory in the store: one path segment, nothing a shell or a path could misread.
_REE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def ree_directory(store: Path, ree_id: str) -> Path:
    """The directory of ``ree_id`` in ``store``; refuses an id that is not one plain path segment."""
    if not _REE_ID.fullmatch(ree_id) or ree_id in {".", ".."}:
        raise ValueError(f"not an REE id: {ree_id!r}")
    return store / ree_id


SCRIPT_RUNNER_VARIABLE = "REPO2REE_SCRIPT_RUNNER"


@dataclass(frozen=True)
class ScriptBackend:
    """Where this workbench runs the author's scripts: on its host, or in a container from each REE's image."""

    backend: str = "host"
    engine: str = "docker"
    # The engine a script can reach: none, or the host's (its socket, or a host script's own).
    script_engine: str = "none"
    engine_path: tuple[str, str] | None = None
    # Whose jobs its containers are: the store this workbench serves.
    owner: str = ""

    def choice(self, workbench_environment: dict[str, object]) -> str:
        """The runner for an REE that declares ``workbench_environment``, or why this workbench cannot run it."""
        image = workbench_environment.get("oci")
        mapped = {"local": self.engine_path[0], "engine": self.engine_path[1]} if self.engine_path else None
        return json.dumps(
            {
                "backend": self.backend,
                "engine": self.engine,
                "image": image or "",
                "script_engine": self.script_engine,
                "engine_path": mapped,
                "owner": self.owner,
                "refused": self.refusal(workbench_environment),
            }
        )

    def refusal(self, workbench_environment: dict[str, object]) -> str | None:
        """Why this workbench cannot run scripts in the REE's declared ``workbench_environment``; None when it can."""
        image = workbench_environment.get("oci")
        if self.backend == "container" and not image:
            return "this workbench runs scripts in a container: declare the OCI image the REE's scripts run in"
        if self.backend == "host" and image:
            return f"this workbench runs scripts on its own machine, and cannot run them in {image}"
        return None

    def remove_leftover_jobs(self, keep: frozenset[str] = frozenset()) -> None:
        """Remove the jobs of this store no running executor awaits: all but those of the executions in ``keep``."""
        if self.backend != "container" or not self.owner:
            return
        listed = subprocess.run(
            [
                self.engine,
                "ps",
                "-a",
                "--filter",
                f"label=repo2ree.job-owner={self.owner}",
                "--format",
                '{{.ID}} {{.Label "repo2ree.job-execution"}}',
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        leftovers = []
        for line in listed.stdout.splitlines():
            container, _, execution = line.strip().partition(" ")
            if container and execution.strip() not in keep:
                leftovers.append(container)
        if leftovers:
            subprocess.run([self.engine, "rm", "-f", *leftovers], check=False, capture_output=True, timeout=120)


def declared_workbench_environment(root: Path) -> dict[str, object]:
    """The workbench environment the REE at ``root`` declares its scripts run in; empty when it declares none."""
    try:
        document = json.loads((root / "ree.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    declared = (document.get("subject") or {}).get("definition", {}).get("workbench_environment")
    return declared if isinstance(declared, dict) else {}


class LocalExecutor:
    """Run executor processes locally, each against one REE of the store."""

    def __init__(
        self,
        root: Path,
        exec_path: str = "repo2ree-exec",
        *,
        environment: dict[str, str] | None = None,
        scripts: ScriptBackend | None = None,
    ) -> None:
        self.root = root.resolve()
        self.exec_path = exec_path
        # What every executor is started with besides this process's own environment (the tools).
        self.tools = environment or {}
        # Where the author's scripts run, and what this workbench refuses to run; None: on this host.
        self.scripts = scripts

    def ree_root(self, ree_id: str) -> Path:
        """The root an REE's commands run against: its directory in the store."""
        return ree_directory(self.root, ree_id)

    def delete_ree(self, ree_id: str) -> None:
        root = self.ree_root(ree_id)
        if root.exists():
            shutil.rmtree(root)

    def environment(self, root: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
        environment = {**os.environ, **self.tools}
        environment["REPO2REE_WORKBENCH_ROOT"] = str(root)
        if self.scripts is not None:
            environment[SCRIPT_RUNNER_VARIABLE] = self.scripts.choice(declared_workbench_environment(root))
        environment.update(extra or {})
        if traceparent := current_traceparent():
            environment["TRACEPARENT"] = traceparent
        return environment

    def build_info(self) -> BuildInfo:
        """Ask the configured executor to identify itself, tolerating older binaries."""
        try:
            result = subprocess.run(
                [self.exec_path, "build-info"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=self.environment(self.root),
            )
            if result.returncode == 0:
                return BuildInfo.model_validate(json.loads(result.stdout))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return BuildInfo()

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str) -> None:
        self.run(self.ree_root(ree_id), argv, timeout)

    def run(self, root: Path, argv: list[str], timeout: int) -> str:
        """Run an executor subcommand against ``root``; its stdout."""
        result = subprocess.run(
            [self.exec_path, *argv],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self.environment(root),
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "(no output)"
            raise RuntimeError(f"executor {argv[0]!r} failed (exit {result.returncode}): {detail}")
        return result.stdout

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str) -> Iterator[bytes]:
        result = subprocess.run(
            [self.exec_path, *argv],
            check=False,
            capture_output=True,
            timeout=timeout,
            env=self.environment(self.ree_root(ree_id)),
        )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")
        view = memoryview(result.stdout)
        for offset in range(0, len(view), 256 * 1024):
            yield bytes(view[offset : offset + 256 * 1024])

    def exec_query_to_file(self, argv: list[str], target: Path, timeout: int = 600, *, ree_id: str) -> None:
        """Run an executor query with its stdout written straight to ``target``, never held in memory."""
        with target.open("wb") as output:
            result = subprocess.run(
                [self.exec_path, *argv],
                check=False,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=self.environment(self.ree_root(ree_id)),
            )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        destination = self._resolve_destination(self.ree_root(ree_id), workbench_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copyfile(source_path, temporary)
            Path(temporary).replace(destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _resolve_destination(root: Path, requested: str) -> Path:
        path = PurePosixPath(requested)
        if ".." in path.parts:
            raise ValueError("workbench path must not contain '..'")
        if path.is_absolute():
            try:
                relative = path.relative_to("/ree")
            except ValueError as exc:
                raise ValueError("absolute workbench paths must be below /ree") from exc
        else:
            relative = path
        destination = root.joinpath(*relative.parts)
        resolved_parent = destination.parent.resolve()
        if not resolved_parent.is_relative_to(root):
            raise ValueError("workbench path escapes the configured root")
        return resolved_parent / destination.name
