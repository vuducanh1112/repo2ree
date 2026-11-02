"""Native executor supervision inside one supplied workbench environment.

A managed bench runs every command against its one root, the REE it was provisioned for. A
workbench serving a store keeps one directory per REE beneath its root and runs each command
against the directory of the REE the request names.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path, PurePosixPath

from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame, ResultFrame
from repo2ree_telemetry.spans import current_traceparent
from repo2ree_workbench import executor_frames

# How long a canceled executor gets to stop by itself — stop its script, roll the REE back,
# capture the attempt, report — before it is signalled. Fixed for now; one place to change it.
CANCEL_GRACE_SECONDS = 10.0
# How long a signalled executor gets after SIGTERM (which it also treats as a cancel) before SIGKILL.
CANCEL_KILL_SECONDS = 5.0
# An REE id names a directory in the store: one path segment, nothing a shell or a path could misread.
_REE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def ree_directory(store: Path, ree_id: str) -> Path:
    """The directory of ``ree_id`` in ``store``; refuses an id that is not one plain path segment."""
    if not _REE_ID.fullmatch(ree_id) or ree_id in {".", ".."}:
        raise ValueError(f"not an REE id: {ree_id!r}")
    return store / ree_id


class LocalExecutor:
    """Run short-lived executor processes locally, against one root or one REE of a store."""

    def __init__(
        self,
        root: Path,
        exec_path: str = "repo2ree-exec",
        *,
        store: bool = False,
        environment: dict[str, str] | None = None,
        cancel_grace: float = CANCEL_GRACE_SECONDS,
        cancel_kill: float = CANCEL_KILL_SECONDS,
    ) -> None:
        self.root = root.resolve()
        self.exec_path = exec_path
        self.store = store
        # What every executor is started with besides this process's own environment (the tools).
        self.environment = environment or {}
        self.cancel_grace = cancel_grace
        self.cancel_kill = cancel_kill
        # Each active run, by the REE root it runs against and its run id: a run id names a run
        # within one REE only, and a store serves many (the API's quick commands share fixed ids).
        self._runs: dict[tuple[Path, str], subprocess.Popen[str]] = {}
        self._runs_lock = threading.Lock()

    def ree_root(self, ree_id: str | None) -> Path:
        """The root an REE's commands run against: its directory in the store, or the one root."""
        if not self.store:
            return self.root
        if ree_id is None:
            raise ValueError("a workbench serving a store runs a command only for a named REE")
        return ree_directory(self.root, ree_id)

    def is_running(self, ree_id: str) -> bool:
        root = self.ree_root(ree_id)
        with self._runs_lock:
            return any(run_root == root for run_root, _ in self._runs)

    def delete_ree(self, ree_id: str) -> None:
        """Remove an REE's directory from the store; refused while one of its runs is active."""
        if not self.store:
            raise RuntimeError("only a workbench serving a store deletes REEs")
        if self.is_running(ree_id):
            raise RuntimeError(f"REE {ree_id!r} has a run in progress")
        root = self.ree_root(ree_id)
        if root.exists():
            shutil.rmtree(root)

    def _environment(self, root: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
        environment = {**os.environ, **self.environment}
        environment["REPO2REE_WORKBENCH_ROOT"] = str(root)
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
                env=self._environment(self.root),
            )
            if result.returncode == 0:
                return BuildInfo.model_validate(json.loads(result.stdout))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return BuildInfo()

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str | None = None) -> None:
        self._run_simple(self.ree_root(ree_id), argv, timeout)

    def _run_simple(self, root: Path, argv: list[str], timeout: int) -> None:
        result = subprocess.run(
            [self.exec_path, *argv],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._environment(root),
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "(no output)"
            raise RuntimeError(f"executor {argv[0]!r} failed (exit {result.returncode}): {detail}")

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str | None = None) -> Iterator[bytes]:
        result = subprocess.run(
            [self.exec_path, *argv],
            check=False,
            capture_output=True,
            timeout=timeout,
            env=self._environment(self.ree_root(ree_id)),
        )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")
        view = memoryview(result.stdout)
        for offset in range(0, len(view), 256 * 1024):
            yield bytes(view[offset : offset + 256 * 1024])

    def exec_query_to_file(
        self, argv: list[str], target: Path, timeout: int = 600, *, ree_id: str | None = None
    ) -> None:
        """Run an executor query with its stdout written straight to ``target``, never held in memory."""
        with target.open("wb") as output:
            result = subprocess.run(
                [self.exec_path, *argv],
                check=False,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=self._environment(self.ree_root(ree_id)),
            )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")

    def exec_action(
        self,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext | None = None,
        *,
        ree_id: str | None = None,
    ) -> Iterator[Frame]:
        root = self.ree_root(ree_id)
        proc = subprocess.Popen(
            [
                self.exec_path,
                "execute",
                "--action",
                "-",
                "--run-id",
                run_id,
                "--execution-context",
                (context or ExecutionContext.new()).model_dump_json(),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self._environment(root, env),
            start_new_session=True,
        )
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            proc.kill()
            raise RuntimeError("executor pipes unavailable")
        stdout = proc.stdout
        with self._runs_lock:
            if (root, run_id) in self._runs:
                proc.kill()
                raise RuntimeError(f"run {run_id!r} is already active")
            self._runs[(root, run_id)] = proc
        try:
            proc.stdin.write(cmd_json)
            proc.stdin.close()
            stdout_parts: list[str] = []
            stdout_reader = threading.Thread(target=lambda: stdout_parts.append(stdout.read()), daemon=True)
            stdout_reader.start()
            for raw_line in proc.stderr:
                if frame := executor_frames.executor_line_to_frame(raw_line.rstrip()):
                    yield frame
            stdout_reader.join()
            proc.wait()
            yield ResultFrame(
                result=executor_frames.parse_action_result("".join(stdout_parts).strip(), proc.returncode or 0)
            )
        finally:
            with self._runs_lock:
                self._runs.pop((root, run_id), None)

    def cancel_run(self, run_id: str, *, ree_id: str | None = None) -> None:
        """Ask the run's executor to stop, and only force it if it does not.

        The cancel marker is cooperative: the executor stops its script, rolls the REE back,
        captures the attempt, and reports it canceled. Killing it at once would abandon the
        attempt mid-execution, or mid-capture. An executor still running after the grace
        period is signalled (SIGTERM, which it treats as a cancel too), then killed.
        """
        # The marker goes where the run reads it: its REE's root.
        root = self.ree_root(ree_id)
        self._run_simple(root, ["cancel-run", "--run-id", run_id], 10)
        with self._runs_lock:
            proc = self._runs.get((root, run_id))
        if proc is not None and proc.poll() is None:
            threading.Thread(target=self._escalate, args=(proc,), name=f"cancel-{run_id}", daemon=True).start()

    def _escalate(self, proc: subprocess.Popen[str]) -> None:
        for sig, wait in ((None, self.cancel_grace), (signal.SIGTERM, self.cancel_kill), (signal.SIGKILL, None)):
            if sig is not None:
                with suppress(ProcessLookupError):
                    os.killpg(proc.pid, sig)
            if wait is None:
                return
            with suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=wait)
                return

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str | None = None) -> None:
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
