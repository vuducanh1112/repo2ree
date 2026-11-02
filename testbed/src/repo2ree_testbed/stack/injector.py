"""The fault channel a stack serves to its client: parse a fault, check it targets this stack, apply it."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from repo2ree_testbed.faults import (
    FAULT,
    CrashApi,
    Fault,
    HealWorkbench,
    KillWorkbench,
    LockHistory,
    MisdirectProviders,
    PartitionWorkbench,
    PauseWorkbench,
    RestoreProviders,
    ResumeWorkbench,
    StopProviders,
    UnlockHistory,
)
from repo2ree_testbed.stack.docker import networks
from repo2ree_testbed.stack.process import capture, fetch_as, run

OWNER_LABEL = "repo2ree.resource-owner"
UNANSWERED = "ws://127.0.0.1:9/workbench/connect"
# What git takes for another process updating the REE's history ref (core's HISTORY_REF), in an
# REE's directory; a provider's bench mounts its one REE at /ree.
HISTORY_LOCK_IN_REE = Path(".git/refs/heads/ree-history.lock")
HISTORY_LOCK = f"/ree/{HISTORY_LOCK_IN_REE}"
# What a fault does to the workbench serving an REE's store.
type WorkbenchFault = Literal["kill", "pause", "resume", "partition", "heal", "lock_history", "unlock_history"]


class _Request(BaseModel):
    model_config = ConfigDict(extra="ignore")

    allocation_id: str
    ree_id: str


class _Allocation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    request: _Request


_ALLOCATIONS = TypeAdapter(dict[str, list[_Allocation]])
_LABELS = TypeAdapter[dict[str, str] | None](dict[str, str] | None)


class FaultUnavailableError(RuntimeError):
    pass


_STORE_ACTIONS: dict[str, WorkbenchFault] = {
    "kill_workbench": "kill",
    "pause_workbench": "pause",
    "resume_workbench": "resume",
    "partition_workbench": "partition",
    "heal_workbench": "heal",
    "lock_history": "lock_history",
    "unlock_history": "unlock_history",
}


class Target(Protocol):
    @property
    def owner(self) -> str: ...

    @property
    def provider_managed(self) -> bool: ...

    def crash_api(self) -> None: ...

    def restart_locations(self, overrides: Mapping[str, str]) -> None: ...

    def stop_locations(self) -> None: ...

    @property
    def api_url(self) -> str: ...

    def workbench_fault(self, ree_id: str, action: WorkbenchFault) -> None: ...


class Injector:
    def __init__(self, target: Target) -> None:
        self.target = target
        self.partitions: dict[str, tuple[str, ...]] = {}
        self.lock = threading.Lock()
        injector = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                try:
                    injector.apply(FAULT.validate_json(body))
                except ValidationError as error:
                    self.answer(HTTPStatus.BAD_REQUEST, str(error))
                except FaultUnavailableError as error:
                    self.answer(HTTPStatus.CONFLICT, str(error))
                else:
                    self.answer(HTTPStatus.OK, "applied")

            def answer(self, status: HTTPStatus, message: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(message.encode())

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's name
                print(f">> fault channel: {format % args}")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.serving = False

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host!s}:{port}/faults"

    def start(self) -> None:
        self.thread.start()
        self.serving = True

    def stop(self) -> None:
        if self.serving:
            self.server.shutdown()
        self.server.server_close()

    def container(self, ree_id: str) -> str:
        """The bench a provider set up for ``ree_id``, as its allocation names it."""
        listed = fetch_as(f"{self.target.api_url}/api/v1/allocations", _ALLOCATIONS, timeout=30) or {"allocations": []}
        allocation_id = next(
            (item.request.allocation_id for item in listed["allocations"] if item.request.ree_id == ree_id), None
        )
        if allocation_id is None:
            raise FaultUnavailableError(f"{ree_id} has no allocation in this stack")
        name = f"repo2ree-wb-{allocation_id}"
        labels = _LABELS.validate_json(capture(["docker", "inspect", "-f", "{{json .Config.Labels}}", name]) or "null")
        if not labels or labels.get(OWNER_LABEL) != self.target.owner:
            raise FaultUnavailableError(f"{name} is not a workbench of this stack")
        return name

    def docker(self, *args: str) -> None:
        result = run(["docker", *args], check=False, capture=True)
        if result.returncode:
            raise FaultUnavailableError(f"docker {' '.join(args)}: {result.stderr.strip()}")

    def apply(self, fault: Fault) -> None:
        print(f">> injecting {fault.kind}")
        with self.lock:
            if not self.target.provider_managed and (action := _STORE_ACTIONS.get(fault.kind)):
                self.target.workbench_fault(fault.ree_id, action)  # type: ignore[union-attr]
                return
            match fault:
                case KillWorkbench(ree_id=allocation):
                    self.docker("kill", self.container(allocation))
                case PauseWorkbench(ree_id=allocation):
                    self.docker("pause", self.container(allocation))
                case ResumeWorkbench(ree_id=allocation):
                    self.docker("unpause", self.container(allocation))
                case PartitionWorkbench(ree_id=allocation):
                    name = self.container(allocation)
                    attached = tuple(networks(name))
                    for network in attached:
                        self.docker("network", "disconnect", network, name)
                    self.partitions[allocation] = attached
                case HealWorkbench(ree_id=allocation):
                    name = self.container(allocation)
                    for network in self.partitions.pop(allocation, ()):
                        self.docker("network", "connect", network, name)
                case LockHistory(ree_id=allocation):
                    self.docker("exec", self.container(allocation), "touch", HISTORY_LOCK)
                case UnlockHistory(ree_id=allocation):
                    self.docker("exec", self.container(allocation), "rm", "-f", HISTORY_LOCK)
                case CrashApi():
                    self.target.crash_api()
                case MisdirectProviders():
                    if not self.target.provider_managed:
                        raise FaultUnavailableError("there is no provider to misdirect")
                    self.target.restart_locations({"PROVIDER_WORKBENCH_API_WS_URL": UNANSWERED})
                case RestoreProviders():
                    self.target.restart_locations({})
                case StopProviders():
                    if not self.target.provider_managed:
                        raise FaultUnavailableError("there is no provider to stop")
                    self.target.stop_locations()
