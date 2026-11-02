from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import DoneFrame, Frame
from repo2ree_workbench.service import WorkbenchService


class _Backend:
    def __init__(self, root: Path | None = None) -> None:
        self.calls: list[str] = []
        self.root = root or Path("/nonexistent-test-root")

    def exec_action(
        self, cmd_json: str, run_id: str, env: dict[str, str], context=None, *, ree_id: str | None = None
    ) -> Iterator[Frame]:
        self.calls.append("exec_action")
        yield DoneFrame()

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str | None = None) -> None:
        self.calls.append("exec_simple")

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str | None = None) -> Iterator[bytes]:
        self.calls.append("exec_query")
        yield b"result"

    def cancel_run(self, run_id: str, *, ree_id: str | None = None) -> None:
        self.calls.append("cancel_run")

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str | None = None) -> None:
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


def test_service_refuses_a_root_left_populated_by_another_allocation(tmp_path: Path) -> None:
    (tmp_path / "ree.json").write_text("{}")
    service = WorkbenchService(_Backend(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="not empty"):
        service.assign(_allocation())


def test_service_assigns_a_root_that_does_not_exist_yet(tmp_path: Path) -> None:
    """An external bench is pointed at a path; ``init-ree`` is what creates it."""
    service = WorkbenchService(_Backend(tmp_path / "external-root"))  # type: ignore[arg-type]

    service.assign(_allocation())
    service.exec_simple(["init-ree", "--name", "demo"])


def test_a_managed_bench_refuses_a_request_for_another_ree(tmp_path: Path) -> None:
    service = WorkbenchService(_Backend(tmp_path))  # type: ignore[arg-type]
    service.assign(_allocation())

    service.exec_simple(["doctor"], ree_id="ree-1")
    with pytest.raises(RuntimeError, match="not 'ree-2'"):
        service.exec_simple(["doctor"], ree_id="ree-2")


def test_a_store_runs_only_requests_that_name_their_ree_and_takes_no_allocation(tmp_path: Path) -> None:
    service = WorkbenchService(_Backend(tmp_path), store_id="lab-a", slots=2)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="named REE"):
        service.exec_simple(["doctor"])
    with pytest.raises(RuntimeError, match="takes no allocation"):
        service.assign(_allocation())
    service.exec_simple(["doctor"], ree_id="ree-1")


def test_a_store_creates_an_ree_only_where_none_is(tmp_path: Path) -> None:
    backend = _Backend(tmp_path)
    backend.ree_root = lambda ree_id: tmp_path / str(ree_id)  # type: ignore[attr-defined]
    service = WorkbenchService(backend, store_id="lab-a")  # type: ignore[arg-type]
    (tmp_path / "ree-1").mkdir()
    (tmp_path / "ree-1" / "ree.json").write_text("{}")

    with pytest.raises(RuntimeError, match="already exists"):
        service.exec_simple(["init-ree", "--name", "demo"], ree_id="ree-1")
    service.exec_simple(["init-ree", "--name", "demo"], ree_id="ree-2")


def _allocation(allocation_id: str = "alloc-1", ree_id: str = "ree-1") -> AllocationRequest:
    return AllocationRequest(
        allocation_id=allocation_id,
        ree_id=ree_id,
        location_id="lab-1",
        image="docker.io/library/docker:29-dind",
    )
