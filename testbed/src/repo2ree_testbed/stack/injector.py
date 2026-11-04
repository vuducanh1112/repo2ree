"""The fault channel a stack serves to its client: parse a fault, check it targets this stack, apply it."""

from __future__ import annotations

import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Literal, Protocol

from pydantic import ValidationError

from repo2ree_testbed.faults import FAULT, CrashApi, Fault

# What git takes for another process updating the REE's history ref (core's HISTORY_REF), in an
# REE's directory.
HISTORY_LOCK_IN_REE = Path(".git/refs/heads/ree-history.lock")
# What a fault does to the workbench serving an REE's store.
type WorkbenchFault = Literal[
    "kill", "pause", "resume", "partition", "heal", "start_rival", "stop_rival", "lock_history", "unlock_history"
]


class FaultUnavailableError(RuntimeError):
    pass


_STORE_ACTIONS: dict[str, WorkbenchFault] = {
    "kill_workbench": "kill",
    "pause_workbench": "pause",
    "resume_workbench": "resume",
    "partition_workbench": "partition",
    "heal_workbench": "heal",
    "start_rival_workbench": "start_rival",
    "stop_rival_workbench": "stop_rival",
    "lock_history": "lock_history",
    "unlock_history": "unlock_history",
}


class Target(Protocol):
    @property
    def owner(self) -> str: ...

    def crash_api(self) -> None: ...

    def workbench_fault(self, ree_id: str, action: WorkbenchFault) -> None: ...


class Injector:
    def __init__(self, target: Target) -> None:
        self.target = target
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

    def apply(self, fault: Fault) -> None:
        print(f">> injecting {fault.kind}")
        with self.lock:
            if isinstance(fault, CrashApi):
                self.target.crash_api()
            else:
                self.target.workbench_fault(fault.ree_id, _STORE_ACTIONS[fault.kind])
