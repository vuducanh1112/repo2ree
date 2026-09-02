"""Native executor supervision inside one supplied workbench environment."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path, PurePosixPath

from repo2ree_protocol.frames import Frame, ResultFrame
from repo2ree_protocol.tracing import current_traceparent
from repo2ree_workbench import executor_frames


class LocalExecutor:
    """Run short-lived executor processes locally against one configured root."""

    def __init__(self, root: Path, exec_path: str = "repo2ree-exec") -> None:
        self.root = root.resolve()
        self.exec_path = exec_path
        self._runs: dict[str, subprocess.Popen[str]] = {}
        self._runs_lock = threading.Lock()

    def _environment(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        environment = dict(os.environ)
        environment["REPO2REE_WORKBENCH_ROOT"] = str(self.root)
        environment.update(extra or {})
        if traceparent := current_traceparent():
            environment["TRACEPARENT"] = traceparent
        return environment

    def exec_simple(self, argv: list[str], timeout: int = 60) -> None:
        result = subprocess.run(
            [self.exec_path, *argv],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._environment(),
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "(no output)"
            raise RuntimeError(f"executor {argv[0]!r} failed (exit {result.returncode}): {detail}")

    def exec_query_stream(self, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        result = subprocess.run(
            [self.exec_path, *argv],
            check=False,
            capture_output=True,
            timeout=timeout,
            env=self._environment(),
        )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")
        view = memoryview(result.stdout)
        for offset in range(0, len(view), 256 * 1024):
            yield bytes(view[offset : offset + 256 * 1024])

    def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]:
        proc = subprocess.Popen(
            [self.exec_path, "execute", "--action", "-", "--run-id", run_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=self._environment(env),
            start_new_session=True,
        )
        if proc.stdin is None or proc.stdout is None or proc.stderr is None:
            proc.kill()
            raise RuntimeError("executor pipes unavailable")
        stdout = proc.stdout
        with self._runs_lock:
            if run_id in self._runs:
                proc.kill()
                raise RuntimeError(f"run {run_id!r} is already active")
            self._runs[run_id] = proc
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
                self._runs.pop(run_id, None)

    def cancel_run(self, run_id: str) -> None:
        # Leave the durable cooperative marker first, then stop the complete
        # executor process group so cancellation also covers a wedged child.
        self.exec_simple(["cancel-run", "--run-id", run_id], timeout=10)
        with self._runs_lock:
            proc = self._runs.get(run_id)
        if proc is not None and proc.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)

    def copy_in(self, source_path: str, workbench_path: str) -> None:
        destination = self._resolve_destination(workbench_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copyfile(source_path, temporary)
            Path(temporary).replace(destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def _resolve_destination(self, requested: str) -> Path:
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
        destination = self.root.joinpath(*relative.parts)
        resolved_parent = destination.parent.resolve()
        if not resolved_parent.is_relative_to(self.root):
            raise ValueError("workbench path escapes the configured root")
        return resolved_parent / destination.name
