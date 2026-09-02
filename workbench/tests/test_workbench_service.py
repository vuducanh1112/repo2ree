from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol import AllocationRequest
from repo2ree_protocol.frames import DoneFrame, Frame
from repo2ree_workbench.service import WorkbenchService


class _Backend:
    def __init__(self, root: Path | None = None) -> None:
        self.calls: list[str] = []
        self.root = root or Path("/nonexistent-test-root")

    def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]:
        self.calls.append("exec_action")
        yield DoneFrame()

    def exec_simple(self, argv: list[str], timeout: int = 60) -> None:
        self.calls.append("exec_simple")

    def exec_query_stream(self, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        self.calls.append("exec_query")
        yield b"result"

    def cancel_run(self, run_id: str) -> None:
        self.calls.append("cancel_run")

    def copy_in(self, source_path: str, workbench_path: str) -> None:
        self.calls.append("copy_in")


def test_service_routes_every_execution_operation(tmp_path: Path) -> None:
    backend = _Backend(tmp_path)
    service = WorkbenchService(backend)  # type: ignore[arg-type]
    service.assign(_allocation())

    assert list(service.exec_action("{}", "run-1", {})) == [DoneFrame()]
    service.exec_simple(["doctor"])
    assert list(service.exec_query_stream(["archive"])) == [b"result"]
    service.cancel_run("run-1")
    service.copy_in("source", "/ree/dest")

    assert backend.calls == [
        "exec_action",
        "exec_simple",
        "exec_query",
        "cancel_run",
        "copy_in",
    ]


def test_service_refuses_execution_until_assigned(tmp_path: Path) -> None:
    backend = _Backend(tmp_path)
    service = WorkbenchService(backend)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="not been assigned"):
        service.exec_simple(["doctor"])

    service.assign(_allocation())
    service.exec_simple(["doctor"])
    with pytest.raises(RuntimeError, match="already assigned"):
        service.assign(_allocation("alloc-2", "ree-2"))


def _allocation(allocation_id: str = "alloc-1", ree_id: str = "ree-1") -> AllocationRequest:
    return AllocationRequest(
        allocation_id=allocation_id,
        ree_id=ree_id,
        location_id="lab-1",
        profile_id="standard",
        profile_revision="1",
    )
