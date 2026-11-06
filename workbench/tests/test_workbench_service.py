from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_workbench.executions import Identity, _Live
from repo2ree_workbench.service import WorkbenchService


class _Backend:
    def __init__(self, root: Path | None = None) -> None:
        self.calls: list[str] = []
        self.root = root or Path("/nonexistent-test-root")

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str) -> None:
        self.calls.append("exec_simple")

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str) -> Iterator[bytes]:
        self.calls.append("exec_query")
        yield b"result"

    def run(self, root: Path, argv: list[str], timeout: int) -> str:
        self.calls.append(argv[0])
        return ""

    def ree_root(self, ree_id: str) -> Path:
        return self.root / ree_id

    def delete_ree(self, ree_id: str) -> None:
        self.calls.append("delete_ree")

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        self.calls.append("copy_in")


def test_service_routes_every_execution_operation_for_the_ree_it_names(tmp_path: Path) -> None:
    backend = _Backend(tmp_path)
    service = WorkbenchService(backend, store_id="lab-a")  # type: ignore[arg-type]

    service.exec_simple(["doctor"], ree_id="ree-1")
    assert list(service.exec_query_stream(["archive"], ree_id="ree-1")) == [b"result"]
    service.cancel_run("run-1", ree_id="ree-1")
    service.copy_in("source", "/ree/dest", ree_id="ree-1")
    service.delete_ree("ree-1")

    assert backend.calls == ["exec_simple", "exec_query", "cancel-run", "copy_in", "delete_ree"]


def test_a_store_deletes_an_ree_only_while_none_of_its_runs_is_active(tmp_path: Path) -> None:
    backend = _Backend(tmp_path)
    service = WorkbenchService(backend, store_id="lab-a")  # type: ignore[arg-type]
    service.executions._live["a1"] = _Live(
        Identity(attempt_id="a1", ree_id="ree-1", run_id="r", operation="o", pid=1), tmp_path
    )

    with pytest.raises(RuntimeError, match="in progress"):
        service.delete_ree("ree-1")
    service.delete_ree("ree-2")
    assert backend.calls == ["delete_ree"]


def test_a_store_creates_an_ree_only_where_none_is(tmp_path: Path) -> None:
    backend = _Backend(tmp_path)
    service = WorkbenchService(backend, store_id="lab-a")  # type: ignore[arg-type]
    (tmp_path / "ree-1").mkdir()
    (tmp_path / "ree-1" / "ree.json").write_text("{}")

    with pytest.raises(RuntimeError, match="already exists"):
        service.exec_simple(["init-ree", "--name", "demo"], ree_id="ree-1")
    service.exec_simple(["init-ree", "--name", "demo"], ree_id="ree-2")


def test_the_service_lists_and_serves_its_store_journals_as_written(tmp_path: Path) -> None:
    from repo2ree_workbench.journal import journal_directory

    directory = journal_directory(tmp_path)
    directory.mkdir(parents=True)
    lines = b'{"v":1,"seq":1,"kind":"journal.opened"}\n{"v":1,"seq":2,"kind":"transition"}\n{"v":1,"seq":3'
    (directory / "workbench-000001.ndjson").write_bytes(lines)
    service = WorkbenchService(_Backend(tmp_path), store_id="lab-a")  # type: ignore[arg-type]

    listed = service.list_journals()
    assert [(item.id, item.process, item.epoch, item.last_seq) for item in listed.journals] == [
        ("workbench-000001", "workbench", 1, 2)
    ]
    assert b"".join(service.read_journal("workbench-000001", 1)) == b'{"v":1,"seq":2,"kind":"transition"}\n'
    with pytest.raises(FileNotFoundError):
        list(service.read_journal("../journal", 0))
