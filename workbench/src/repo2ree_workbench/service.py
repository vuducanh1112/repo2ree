"""Execution service for the store this workbench serves.

Every request names its REE, and the REE's directory in the store is where its commands run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame
from repo2ree_workbench.executor_process import LocalExecutor

INIT_REE = "init-ree"


class WorkbenchService:
    """The backend-neutral execution service of a store's workbench."""

    def __init__(self, executor: LocalExecutor, *, store_id: str, slots: int = 1):
        self._executor = executor
        self.store_id = store_id
        self.slots = slots
        # Actions wait here for a slot; queries do not.
        self.action_slots = asyncio.Semaphore(slots)

    def exec_action(
        self,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext | None = None,
        *,
        ree_id: str,
    ) -> Iterator[Frame]:
        return self._executor.exec_action(cmd_json, run_id, env, context, ree_id=ree_id)

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str) -> None:
        if argv[:1] == [INIT_REE]:
            root = self._executor.ree_root(ree_id)
            if root.exists() and any(root.iterdir()):
                raise RuntimeError(f"REE {ree_id!r} already exists in store {self.store_id!r}")
        self._executor.exec_simple(argv, timeout, ree_id=ree_id)

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str) -> Iterator[bytes]:
        return self._executor.exec_query_stream(argv, timeout, ree_id=ree_id)

    def exec_query_to_file(self, argv: list[str], target: Path, timeout: int = 600, *, ree_id: str) -> None:
        self._executor.exec_query_to_file(argv, target, timeout, ree_id=ree_id)

    def cancel_run(self, run_id: str, *, ree_id: str) -> None:
        self._executor.cancel_run(run_id, ree_id=ree_id)

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        self._executor.copy_in(source_path, workbench_path, ree_id=ree_id)

    def delete_ree(self, ree_id: str) -> None:
        self._executor.delete_ree(ree_id)
