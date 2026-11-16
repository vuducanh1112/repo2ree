"""Execution service for the store this workbench serves.

Every request names its REE, and the REE's directory in the store is where its commands run.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.queries import REPLIES, BundleQuery, InitRee, Query, query_argv
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import WorkbenchJournal, WorkbenchJournalList
from repo2ree_telemetry.behaviour import journal_file, journal_files, positions, records_after
from repo2ree_workbench.cli_process import LocalCli
from repo2ree_workbench.executions import Executions, LogFollower
from repo2ree_workbench.journal import journal_directory

JOURNAL_CHUNK = 256 * 1024


class WorkbenchService:
    """The backend-neutral execution service of a store's workbench."""

    def __init__(self, executor: LocalCli, *, store_id: str, slots: int = 1, executions: Executions | None = None):
        self._executor = executor
        self.store_id = store_id
        self.slots = slots
        # Commands wait for one of the slots; queries do not.
        self.executions = executions or Executions(executor, slots=slots)

    async def start_run(
        self,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext,
        *,
        ree_id: str,
        wait: float = 0.0,
    ) -> None:
        await self.executions.start(cmd_json, run_id, env, context, ree_id=ree_id, wait=wait)

    def follow_run(self, ree_id: str, attempt_id: str, after: int) -> LogFollower:
        return self.executions.follow(ree_id, attempt_id, after)

    def init_ree(self, init: InitRee, timeout: int = 60, *, ree_id: str) -> None:
        """Create the REE in the store; refused where one is already."""
        root = self._executor.ree_root(ree_id)
        if root.exists() and any(root.iterdir()):
            raise RuntimeError(f"REE {ree_id!r} already exists in store {self.store_id!r}")
        argv, _stdin = query_argv(init)
        self._executor.run(root, argv, timeout)

    def exec_query_stream(self, query: Query, timeout: int = 30, *, ree_id: str) -> Iterator[bytes]:
        """The answer to ``query``: the bytes ``ree`` writes for it, or the outputs of its one result line."""
        argv, stdin = query_argv(query)
        if REPLIES[type(query)] is None:
            return self._executor.exec_query_stream(argv, timeout, ree_id=ree_id, stdin=stdin)
        output = b"".join(self._executor.exec_query_stream(["--json", *argv], timeout, ree_id=ree_id, stdin=stdin))
        return iter((json.dumps(ActionResult.model_validate_json(output).outputs).encode(),))

    def exec_query_to_file(self, query: BundleQuery, target: Path, timeout: int = 600, *, ree_id: str) -> None:
        argv, _stdin = query_argv(query)
        self._executor.exec_query_to_file(argv, target, timeout, ree_id=ree_id)

    def cancel_run(self, run_id: str, *, ree_id: str, record: str | None = None) -> None:
        self.executions.cancel(run_id, ree_id=ree_id, record=record)

    def list_journals(self) -> WorkbenchJournalList:
        directory = journal_directory(self._executor.root)
        last = positions(directory)
        return WorkbenchJournalList(
            journals=[
                WorkbenchJournal(id=file.id, process=file.process, epoch=file.epoch, last_seq=last.get(file.id, 0))
                for file in journal_files(directory)
            ]
        )

    def read_journal(self, journal_id: str, after: int) -> Iterator[bytes]:
        file = journal_file(journal_directory(self._executor.root), journal_id)
        if file is None:
            raise FileNotFoundError(f"no behaviour journal {journal_id} in store {self.store_id!r}")
        data = records_after(file.path, after)
        for offset in range(0, len(data), JOURNAL_CHUNK):
            yield data[offset : offset + JOURNAL_CHUNK]

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        self._executor.copy_in(source_path, workbench_path, ree_id=ree_id)

    def delete_ree(self, ree_id: str) -> None:
        """Remove an REE's directory from the store; refused while one of its runs is active."""
        if self.executions.holds(ree_id):
            raise RuntimeError(f"REE {ree_id!r} has a run in progress")
        self._executor.delete_ree(ree_id)
