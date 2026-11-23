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

from repo2ree_protocol.command import command_adapter
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.verbs import to_argv
from repo2ree_telemetry.behaviour import events
from repo2ree_workbench import cli_events
from repo2ree_workbench.cli_process import LocalCli
from repo2ree_workbench.journal import STATE

CANCEL_GRACE_SECONDS = 10.0
CANCEL_KILL_SECONDS = 5.0
POLL_SECONDS = 0.5
KEPT_SECONDS = 7 * 24 * 3600
_WRAPPER = (
    "sh",
    "-c",
    (
        '"$@" < stdin > result.json 2>> log & child=$!; trap : TERM; '
        'while :; do wait "$child"; status=$?; kill -0 "$child" 2>/dev/null || break; done; '
        'echo "$status" > exit.part && mv exit.part exit'
    ),
    "repo2ree-execution",
)
_FOLLOW_LINES = 500


class ReeBusyError(RuntimeError):
    pass


class UnknownExecutionError(LookupError):
    pass


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    ree_id: str
    run_id: str
    operation: str
    dispatched_by: str | None = None
    pid: int
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
    def __init__(
        self,
        executor: LocalCli,
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
        words, stdin = to_argv(command_adapter.validate_json(cmd_json))
        (directory / "stdin").write_bytes(stdin or b"")
        root = self._executor.ree_root(ree_id)
        argv = [
            *_WRAPPER,
            *self._executor.at(root, ["--json", "--run-id", run_id, "--context", context.model_dump_json(), *words]),
        ]
        process = subprocess.Popen(
            argv,
            cwd=directory,
            env=self._executor.environment(root, env),
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
        directory = self.directory / identity.attempt_id
        argv = ["--json", "--run-id", identity.run_id]
        with suppress(OSError):
            argv += ["--context", (directory / "context.json").read_text(encoding="utf-8")]
        argv += ["settle", identity.attempt_id]
        if (directory / "command.json").is_file():
            argv += ["--command", str(directory / "command.json")]
        try:
            output = self._executor.run(self._executor.ree_root(identity.ree_id), argv, 600)
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return None
        try:
            return ActionResult.model_validate_json(output) if output.strip() else None
        except ValueError:
            return None

    def reconcile(self) -> set[str]:
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
        root = self._executor.ree_root(ree_id)
        self._executor.run(root, ["cancel", run_id], 10)
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
    def __init__(self, directory: Path, after: int) -> None:
        self._directory = directory
        self._skip = after
        self._position = 0
        self._partial = b""

    def read(self) -> tuple[list[Frame], ActionResult | None]:
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
                    if frame := cli_events.cli_line_to_frame(line.decode(errors="replace").rstrip()):
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
