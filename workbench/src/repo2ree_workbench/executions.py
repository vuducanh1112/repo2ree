"""The executors a store's workbench starts apart from itself, so that they outlive it, and how each ended.

Each execution keeps a directory in the store: the command, who runs it, the executor's log, and
once it ended, how. The executor writes its own exit status there, so a workbench process that did
not start it can still tell how it ended. A workbench process starting on the store adopts the
executors the last one left running, and settles the ones it finds gone.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame
from repo2ree_protocol.result import ActionResult
from repo2ree_telemetry.behaviour import events
from repo2ree_workbench import executor_frames
from repo2ree_workbench.executor_process import LocalExecutor
from repo2ree_workbench.journal import STATE

# How long a canceled executor gets to stop by itself — stop its script, roll the REE back,
# capture the attempt, report — before it is signalled.
CANCEL_GRACE_SECONDS = 10.0
# How long a signalled executor gets after SIGTERM (which it also treats as a cancel) before SIGKILL.
CANCEL_KILL_SECONDS = 5.0
# How often an executor this process did not start is looked for, and a follow looks for new lines.
POLL_SECONDS = 0.5
# Endings kept for a follow that comes late, before their directories go.
KEPT_SECONDS = 7 * 24 * 3600
# The executor's container jobs carry their execution, so a restarted workbench keeps the adopted ones'.
EXECUTION_VARIABLE = "REPO2REE_EXECUTION"
# Runs the executor with its command on stdin, its result and log in files, and its exit status
# written once it ends. It outlives the SIGTERM a cancel sends the executor's process group, so it
# lives to write it, without passing the executor a signal it ignores.
_WRAPPER = (
    "sh",
    "-c",
    (
        '"$@" < command.json > result.json 2>> log & child=$!; trap : TERM; '
        'while :; do wait "$child"; status=$?; kill -0 "$child" 2>/dev/null || break; done; '
        'echo "$status" > exit.part && mv exit.part exit'
    ),
    "repo2ree-execution",
)
_FOLLOW_LINES = 500


class ReeBusyError(RuntimeError):
    """Another execution holds the REE."""


class UnknownExecutionError(LookupError):
    """The store holds no execution of the attempt."""


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    ree_id: str
    run_id: str
    operation: str
    dispatched_by: str | None = None
    pid: int
    # When the process started, as the kernel counts it: a pid reused by another process is not it.
    birth: str | None = None
    state: Literal["started", "adopted"] = "started"


class Ending(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["exited", "stopped", "lost"]
    result: ActionResult
    journaled: bool = False


class Stop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: str | None = None


@dataclass
class _Live:
    identity: Identity
    directory: Path
    process: subprocess.Popen[bytes] | None = None
    ended: threading.Event = field(default_factory=threading.Event)


class Executions:
    """The store's executions: started, adopted, followed, stopped, and settled."""

    def __init__(
        self,
        executor: LocalExecutor,
        *,
        slots: int = 1,
        poll: float = POLL_SECONDS,
        cancel_grace: float = CANCEL_GRACE_SECONDS,
        cancel_kill: float = CANCEL_KILL_SECONDS,
    ) -> None:
        self._executor = executor
        self.directory = executor.root / STATE / "executions"
        self.slots = slots
        self.poll = poll
        self.cancel_grace = cancel_grace
        self.cancel_kill = cancel_kill
        self._live: dict[str, _Live] = {}
        self._lock = threading.Lock()

    def holds(self, ree_id: str) -> bool:
        with self._lock:
            return any(live.identity.ree_id == ree_id for live in self._live.values())

    def wait(self, attempt_id: str, timeout: float | None = None) -> bool:
        """Whether the execution of ``attempt_id`` is over, waiting up to ``timeout`` for it."""
        with self._lock:
            live = self._live.get(attempt_id)
        return live is None or live.ended.wait(timeout)

    async def start(
        self,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext,
        *,
        ree_id: str,
        wait: float = 0.0,
    ) -> None:
        """Start the command once a slot is free; refused while another execution holds the REE past ``wait``."""
        deadline = time.monotonic() + wait
        while True:
            with self._lock:
                held = any(live.identity.ree_id == ree_id for live in self._live.values())
                if held and time.monotonic() >= deadline:
                    raise ReeBusyError(f"REE {ree_id!r} has a run in progress")
                if not held and len(self._live) < self.slots:
                    self._launch(cmd_json, run_id, env, context, ree_id)
                    return
            await asyncio.sleep(self.poll)

    def _launch(self, cmd_json: str, run_id: str, env: dict[str, str], context: ExecutionContext, ree_id: str) -> None:
        attempt_id = context.attempt_id
        directory = self.directory / attempt_id
        directory.mkdir(parents=True)
        (directory / "command.json").write_text(cmd_json, encoding="utf-8")
        (directory / "context.json").write_text(context.model_dump_json(), encoding="utf-8")
        argv = [
            *_WRAPPER,
            self._executor.exec_path,
            "execute",
            "--action",
            "-",
            "--run-id",
            run_id,
            "--execution-context",
            context.model_dump_json(),
        ]
        root = self._executor.ree_root(ree_id)
        process = subprocess.Popen(
            argv,
            cwd=directory,
            env=self._executor.environment(root, {**env, EXECUTION_VARIABLE: attempt_id}),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        identity = Identity(
            attempt_id=attempt_id,
            ree_id=ree_id,
            run_id=run_id,
            operation=_operation(cmd_json),
            dispatched_by=context.dispatch_record,
            pid=process.pid,
            birth=_birth(process.pid),
        )
        _write(directory / "identity.json", identity)
        events.execution(
            attempt_id,
            None,
            "started",
            partition=ree_id,
            facts={"operation": identity.operation, "run_id": run_id, "dispatched_by": identity.dispatched_by},
        )
        self._watch(_Live(identity, directory, process))

    def _watch(self, live: _Live) -> None:
        self._live[live.identity.attempt_id] = live
        name = f"execution-{live.identity.attempt_id}"
        threading.Thread(target=self._await_end, args=(live,), name=name, daemon=True).start()

    def _await_end(self, live: _Live) -> None:
        if live.process is not None:
            live.process.wait()
        else:
            while _alive(live.identity):
                time.sleep(self.poll)
        self._end(live)

    def _end(self, live: _Live) -> None:
        identity = live.identity
        ending = self._ending(live.directory, identity)
        _write(live.directory / "ending.json", ending)
        self._journal(identity, ending, live.directory)
        with self._lock:
            self._live.pop(identity.attempt_id, None)
        live.ended.set()

    def _journal(self, identity: Identity, ending: Ending, directory: Path) -> None:
        result = ending.result
        history = result.history
        interrupted = history is not None and history.operation_status == "interrupted"
        facts: events.ExecutionFacts = {"status": "interrupted" if interrupted else result.status}
        if history is not None:
            facts["commit"] = history.after_snapshot_id
            facts["record"] = history.record_digest
        if ending.state == "lost":
            facts["reason"] = "vanished"
        else:
            facts["exit_code"] = _exit_status(directory)
        if ending.state == "stopped":
            stop = _read(directory / "stop.json", Stop) or Stop()
            facts |= {"cause": "cancel", "canceled_by": stop.record}
        events.execution(identity.attempt_id, identity.state, ending.state, partition=identity.ree_id, facts=facts)
        _write(directory / "ending.json", ending.model_copy(update={"journaled": True}))

    def _ending(self, directory: Path, identity: Identity) -> Ending:
        exit_code = _exit_code(directory)
        result = _result(directory)
        if result is None:
            result = self._settle(identity) or ActionResult.failed(
                "internal",
                f"executor produced no valid result (exit {exit_code})",
                origin="workbench",
                exit_code=exit_code or 1,
            )
        if (directory / "stop.json").exists():
            return Ending(state="stopped", result=result)
        return Ending(state="lost" if exit_code is None else "exited", result=result)

    def _settle(self, identity: Identity) -> ActionResult | None:
        """Have core settle the attempt of an executor that ended without reporting."""
        directory = self.directory / identity.attempt_id
        argv = ["settle-attempt", "--attempt-id", identity.attempt_id, "--run-id", identity.run_id]
        if (directory / "command.json").is_file():
            argv += ["--action", str(directory / "command.json")]
        with suppress(OSError):
            argv += ["--execution-context", (directory / "context.json").read_text(encoding="utf-8")]
        try:
            output = self._executor.run(self._executor.ree_root(identity.ree_id), argv, 600)
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return None
        try:
            return ActionResult.model_validate_json(output) if output.strip() else None
        except ValueError:
            return None

    def reconcile(self) -> set[str]:
        """Adopt the executors a previous process of this store left running, and settle the rest.

        Returns the attempts of the adopted ones.
        """
        adopted: set[str] = set()
        if not self.directory.is_dir():
            return adopted
        for directory in sorted(path for path in self.directory.iterdir() if path.is_dir()):
            identity = _read(directory / "identity.json", Identity)
            ending = _read(directory / "ending.json", Ending)
            if identity is None:
                if time.time() - directory.stat().st_mtime > KEPT_SECONDS:
                    shutil.rmtree(directory, ignore_errors=True)
                continue
            if ending is not None:
                if not ending.journaled:
                    self._journal(identity, ending, directory)
                elif time.time() - (directory / "ending.json").stat().st_mtime > KEPT_SECONDS:
                    shutil.rmtree(directory, ignore_errors=True)
                continue
            if _alive(identity):
                events.execution(identity.attempt_id, identity.state, "adopted", partition=identity.ree_id, facts={})
                identity = identity.model_copy(update={"state": "adopted"})
                _write(directory / "identity.json", identity)
                with self._lock:
                    self._watch(_Live(identity, directory))
                adopted.add(identity.attempt_id)
            else:
                self._end(_Live(identity, directory))
        return adopted

    def follow(self, ree_id: str, attempt_id: str, after: int) -> LogFollower:
        directory = self.directory / attempt_id
        identity = _read(directory / "identity.json", Identity)
        if identity is None or identity.ree_id != ree_id:
            raise UnknownExecutionError(f"store holds no execution of attempt {attempt_id!r} in REE {ree_id!r}")
        return LogFollower(directory, after)

    def cancel(self, run_id: str, *, ree_id: str, record: str | None = None) -> None:
        """Ask the run's executor to stop, and only force it if it does not.

        The cancel marker is cooperative: the executor stops its script, rolls the REE back,
        captures the attempt, and reports it canceled. An executor still running after the grace
        period is signalled (SIGTERM, which it treats as a cancel too), then killed. A run not
        started yet finds the marker when it starts.
        """
        root = self._executor.ree_root(ree_id)
        self._executor.run(root, ["cancel-run", "--run-id", run_id], 10)
        with self._lock:
            running = (item for item in self._live.values() if item.identity.ree_id == ree_id)
            live = next((item for item in running if item.identity.run_id == run_id), None)
            if live is None:
                return
            stop = live.directory / "stop.json"
            first = not stop.exists()
            if first:
                _write(stop, Stop(record=record))
        if first:
            threading.Thread(target=self._escalate, args=(live,), name=f"cancel-{run_id}", daemon=True).start()

    def _escalate(self, live: _Live) -> None:
        for sig, wait in ((None, self.cancel_grace), (signal.SIGTERM, self.cancel_kill), (signal.SIGKILL, None)):
            if sig is not None:
                with suppress(ProcessLookupError, PermissionError):
                    os.killpg(live.identity.pid, sig)
            if wait is None or live.ended.wait(wait):
                return


class LogFollower:
    """A started command's log from one line on, and how the command ended once it has."""

    def __init__(self, directory: Path, after: int) -> None:
        self._directory = directory
        self._skip = after
        self._position = 0
        self._partial = b""

    def read(self) -> tuple[list[Frame], ActionResult | None]:
        """The log's new complete lines as frames, and once they are all read, how the command ended."""
        ending = _read(self._directory / "ending.json", Ending)
        frames: list[Frame] = []
        log = self._directory / "log"
        if log.exists():
            with log.open("rb") as stream:
                stream.seek(self._position)
                while len(frames) < _FOLLOW_LINES and (chunk := stream.readline()):
                    self._position += len(chunk)
                    if not chunk.endswith(b"\n"):
                        self._partial += chunk
                        continue
                    line, self._partial = self._partial + chunk, b""
                    if self._skip:
                        self._skip -= 1
                        continue
                    if frame := executor_frames.executor_line_to_frame(line.decode(errors="replace").rstrip()):
                        frames.append(frame)
        done = ending is not None and len(frames) < _FOLLOW_LINES
        return frames, ending.result if done and ending is not None else None


def _operation(cmd_json: str) -> str:
    try:
        operation = json.loads(cmd_json).get("operation")
    except (ValueError, AttributeError):
        return ""
    return operation if isinstance(operation, str) else ""


def _birth(pid: int) -> str | None:
    """When the process started, in clock ticks since boot; None where the kernel does not say."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    return stat.rsplit(")", 1)[1].split()[19]


def _alive(identity: Identity) -> bool:
    try:
        stat = Path(f"/proc/{identity.pid}/stat").read_text()
    except FileNotFoundError:
        return False
    except OSError:
        try:
            os.kill(identity.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    fields = stat.rsplit(")", 1)[1].split()
    return fields[0] != "Z" and (identity.birth is None or fields[19] == identity.birth)


def _exit_code(directory: Path) -> int | None:
    try:
        return int((directory / "exit").read_text().strip())
    except (OSError, ValueError):
        return None


def _exit_status(directory: Path) -> int:
    """The executor's exit status; a stop that killed it with its wrapper left none, as a kill does."""
    code = _exit_code(directory)
    return -signal.SIGKILL if code is None else code


def _result(directory: Path) -> ActionResult | None:
    try:
        text = (directory / "result.json").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return ActionResult.model_validate_json(text.splitlines()[-1])
    except ValueError:
        return None


def _read[Model: BaseModel](path: Path, model: type[Model]) -> Model | None:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, model: BaseModel) -> None:
    partial = path.with_name(f".{path.name}.part")
    partial.write_text(model.model_dump_json(), encoding="utf-8")
    partial.replace(path)
