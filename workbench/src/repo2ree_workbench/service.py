"""Execution service for the environment containing this workbench.

A managed bench is assigned the one allocation it was provisioned for, and its root is that
allocation's REE. A workbench serving a store takes no allocation: every request names its REE,
and the REE's directory in the store is where its commands run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame
from repo2ree_workbench.executor_process import LocalExecutor

INIT_REE = "init-ree"


class WorkbenchService:
    """The backend-neutral execution service for connected workbenches."""

    def __init__(self, executor: LocalExecutor, *, store_id: str = "", slots: int = 1):
        self._executor = executor
        self._assignment: AllocationRequest | None = None
        self.store_id = store_id
        self.slots = slots
        # Actions wait here for a slot; queries do not.
        self.action_slots = asyncio.Semaphore(slots)

    def assign(self, allocation: AllocationRequest) -> None:
        if self.store_id:
            raise RuntimeError("a workbench serving a store takes no allocation")
        if self._assignment is not None:
            if self._assignment == allocation:
                return
            raise RuntimeError("workbench is already assigned to a different allocation")
        # The guard is against inheriting another allocation's tree, so a root
        # that does not exist yet passes it: an externally managed bench is
        # pointed at a path its operator chose, and ``init-ree`` creates the
        # tree there. Only an existing, populated root is a refusal.
        root = self._executor.root
        if root.exists() and any(root.iterdir()):
            raise RuntimeError("unassigned workbench root is not empty")
        self._assignment = allocation

    def _bound(self, ree_id: str | None) -> str | None:
        """The REE a request runs against, once this workbench may run it there."""
        if self.store_id:
            if ree_id is None:
                raise RuntimeError("a workbench serving a store runs a request only for a named REE")
            return ree_id
        if self._assignment is None:
            raise RuntimeError("workbench has not been assigned")
        if ree_id is not None and ree_id != self._assignment.ree_id:
            raise RuntimeError(f"workbench is assigned to REE {self._assignment.ree_id!r}, not {ree_id!r}")
        return None

    def exec_action(
        self,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext | None = None,
        *,
        ree_id: str | None = None,
    ) -> Iterator[Frame]:
        return self._executor.exec_action(cmd_json, run_id, env, context, ree_id=self._bound(ree_id))

    def exec_simple(self, argv: list[str], timeout: int = 60, *, ree_id: str | None = None) -> None:
        bound = self._bound(ree_id)
        if self.store_id and argv[:1] == [INIT_REE]:
            root = self._executor.ree_root(bound)
            if root.exists() and any(root.iterdir()):
                raise RuntimeError(f"REE {bound!r} already exists in store {self.store_id!r}")
        self._executor.exec_simple(argv, timeout, ree_id=bound)

    def exec_query_stream(self, argv: list[str], timeout: int = 30, *, ree_id: str | None = None) -> Iterator[bytes]:
        return self._executor.exec_query_stream(argv, timeout, ree_id=self._bound(ree_id))

    def exec_query_to_file(
        self, argv: list[str], target: Path, timeout: int = 600, *, ree_id: str | None = None
    ) -> None:
        self._executor.exec_query_to_file(argv, target, timeout, ree_id=self._bound(ree_id))

    def cancel_run(self, run_id: str, *, ree_id: str | None = None) -> None:
        self._executor.cancel_run(run_id, ree_id=ree_id if self.store_id else None)

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str | None = None) -> None:
        self._executor.copy_in(source_path, workbench_path, ree_id=self._bound(ree_id))

    def delete_ree(self, ree_id: str) -> None:
        if not self.store_id:
            raise RuntimeError("only a workbench serving a store deletes REEs")
        self._executor.delete_ree(ree_id)
