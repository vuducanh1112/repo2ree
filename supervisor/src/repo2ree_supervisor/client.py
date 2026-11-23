from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import ErrorFrame, Frame, UnavailableFrame
from repo2ree_protocol.queries import BundleQuery, InitRee, Query
from repo2ree_supervisor.transfers import ReceivedFile


class WorkbenchUnavailableError(RuntimeError):
    pass


class ReeBusyError(RuntimeError):
    pass


def raise_for_terminal_error(frame: Frame) -> None:
    if isinstance(frame, UnavailableFrame):
        raise WorkbenchUnavailableError(frame.detail)
    if isinstance(frame, ErrorFrame):
        raise RuntimeError(frame.detail)


class WorkbenchClient(Protocol):
    def init_ree(self, workbench_id: str, init: InitRee, timeout: int = 60, *, ree_id: str) -> None: ...

    def exec_query(self, workbench_id: str, query: Query, timeout: int = 30, *, ree_id: str) -> bytes: ...

    def exec_query_stream(
        self, workbench_id: str, query: Query, timeout: int = 30, *, ree_id: str
    ) -> Iterator[bytes]: ...

    def exec_upload(
        self, workbench_id: str, query: BundleQuery, timeout: int = 600, *, ree_id: str
    ) -> ReceivedFile: ...

    def start_run(
        self,
        workbench_id: str,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext,
        *,
        ree_id: str,
        session: str | None = None,
        wait: float = 0.0,
    ) -> Iterator[Frame]: ...

    def follow_run(
        self, workbench_id: str, attempt_id: str, after: int, *, ree_id: str, session: str | None = None
    ) -> Iterator[Frame]: ...

    def cancel_run(self, workbench_id: str, run_id: str, *, ree_id: str, record: str | None = None) -> None: ...

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str, *, ree_id: str) -> None: ...

    def delete_ree(self, workbench_id: str, ree_id: str) -> None: ...

    def is_connected(self, workbench_id: str) -> bool: ...

    def session_of(self, workbench_id: str) -> str | None: ...
