"""The fault channel a stack serves to its client: parse a fault, check it targets this stack, apply it."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol

from pydantic import TypeAdapter, ValidationError

from repo2ree_testbed.faults import (
    FAULT,
    CrashApi,
    Fault,
    HealWorkbench,
    KillWorkbench,
    MisdirectProviders,
    PartitionWorkbench,
    PauseWorkbench,
    RestoreProviders,
    ResumeWorkbench,
)
from repo2ree_testbed.stack.docker import networks
from repo2ree_testbed.stack.process import capture, run

OWNER_LABEL = "repo2ree.resource-owner"
UNANSWERED = "ws://127.0.0.1:9/workbench/connect"
_LABELS = TypeAdapter[dict[str, str] | None](dict[str, str] | None)


class FaultUnavailableError(RuntimeError):
    pass


class Target(Protocol):
    @property
    def owner(self) -> str: ...

    @property
    def provider_managed(self) -> bool: ...

    def crash_api(self) -> None: ...

    def restart_locations(self, overrides: Mapping[str, str]) -> None: ...


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

    def container(self, allocation_id: str) -> str:
        if not self.target.provider_managed:
            raise FaultUnavailableError("workbench faults need provider-managed benches")
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
            match fault:
                case KillWorkbench(allocation_id=allocation):
                    self.docker("kill", self.container(allocation))
                case PauseWorkbench(allocation_id=allocation):
                    self.docker("pause", self.container(allocation))
                case ResumeWorkbench(allocation_id=allocation):
                    self.docker("unpause", self.container(allocation))
                case PartitionWorkbench(allocation_id=allocation):
                    name = self.container(allocation)
                    attached = tuple(networks(name))
                    for network in attached:
                        self.docker("network", "disconnect", network, name)
                    self.partitions[allocation] = attached
                case HealWorkbench(allocation_id=allocation):
                    name = self.container(allocation)
                    for network in self.partitions.pop(allocation, ()):
                        self.docker("network", "connect", network, name)
                case CrashApi():
                    self.target.crash_api()
                case MisdirectProviders():
                    if not self.target.provider_managed:
                        raise FaultUnavailableError("there is no provider to misdirect")
                    self.target.restart_locations({"PROVIDER_WORKBENCH_API_WS_URL": UNANSWERED})
                case RestoreProviders():
                    self.target.restart_locations({})
