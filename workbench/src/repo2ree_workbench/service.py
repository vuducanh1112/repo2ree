"""Execution service for the one environment containing this workbench."""

from __future__ import annotations

from collections.abc import Iterator

from repo2ree_protocol.frames import Frame
from repo2ree_workbench.executor_process import LocalExecutor


class WorkbenchService:
    """The backend-neutral execution service for connected workbenches."""

    def __init__(self, executor: LocalExecutor, *, bound: bool = True):
        self._executor = executor
        self._bound = bound
        self._allocation_id = ""

    def bind(self, allocation_id: str, ree_id: str) -> None:
        if self._bound:
            raise RuntimeError("workbench is already assigned")
        if any(self._executor.root.iterdir()):
            raise RuntimeError("external workbench root is not empty")
        self._allocation_id = allocation_id
        self._bound = True

    def _require_bound(self) -> None:
        if not self._bound:
            raise RuntimeError("external workbench has not been assigned")

    def exec_action(self, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]:
        self._require_bound()
        return self._executor.exec_action(cmd_json, run_id, env)

    def exec_simple(self, argv: list[str], timeout: int = 60) -> None:
        self._require_bound()
        self._executor.exec_simple(argv, timeout)

    def exec_query_stream(self, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        self._require_bound()
        return self._executor.exec_query_stream(argv, timeout)

    def cancel_run(self, run_id: str) -> None:
        self._executor.cancel_run(run_id)

    def copy_in(self, source_path: str, workbench_path: str) -> None:
        self._require_bound()
        self._executor.copy_in(source_path, workbench_path)
