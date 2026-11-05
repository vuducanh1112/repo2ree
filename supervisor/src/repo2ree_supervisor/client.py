"""The control plane's client of the workbenches serving stores.

The workbench dials the control plane and holds one outbound socket — it never
listens, so it works from inside clusters and NATed networks that only permit
egress. Streaming calls yield typed ``Frame`` records; request/response calls
return plain values and raise ``WorkbenchUnavailableError`` when the workbench
reports the backend is gone.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import ErrorFrame, Frame, UnavailableFrame
from repo2ree_supervisor.transfers import ReceivedFile


class WorkbenchUnavailableError(RuntimeError):
    """Raised when the workbench reports the workbench backend is gone or stopping."""


def raise_for_terminal_error(frame: Frame) -> None:
    """Translate a terminal error frame into the caller-facing exception.

    The two failure frames mean different things to the control plane: an
    ``UnavailableFrame`` is the backend being gone (a 503-shaped, retryable
    condition) while an ``ErrorFrame`` is an operation failure. Both the manager
    and ``WsWorkbenchClient`` map them the same way, so the mapping lives here."""
    if isinstance(frame, UnavailableFrame):
        raise WorkbenchUnavailableError(frame.detail)
    if isinstance(frame, ErrorFrame):
        raise RuntimeError(frame.detail)


class WorkbenchClient(Protocol):
    """The verbs the control plane needs to drive REE commands in a workbench.

    The ``workbench_id`` routes directly to the resident process; ``ree_id`` names the REE in
    the store it serves.
    """

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60, *, ree_id: str) -> None:
        """Run an executor subcommand in the bench, discarding output.

        ``argv`` is the ``repo2ree-exec`` subcommand argv *without* the executor
        binary — the serving backend prepends the bench's entry point."""
        ...

    def exec_query(self, workbench_id: str, argv: list[str], timeout: int = 30, *, ree_id: str) -> bytes: ...

    def exec_query_stream(
        self, workbench_id: str, argv: list[str], timeout: int = 30, *, ree_id: str
    ) -> Iterator[bytes]: ...

    def exec_upload(self, workbench_id: str, argv: list[str], timeout: int = 600, *, ree_id: str) -> ReceivedFile:
        """Run an executor subcommand in the bench and receive its stdout as a file.

        The bytes travel over HTTP beside the control socket (see
        ``repo2ree_supervisor.transfers``), never as frames on it; the caller owns
        the returned file and removes it."""
        ...

    def exec_action(
        self,
        workbench_id: str,
        cmd_json: str,
        run_id: str,
        env: dict[str, str],
        context: ExecutionContext | None = None,
        *,
        ree_id: str,
        session: str | None = None,
    ) -> Iterator[Frame]:
        """Send a command; with ``session``, only on that session of the workbench's connection."""
        ...

    def cancel_run(self, workbench_id: str, run_id: str, *, ree_id: str, record: str | None = None) -> None: ...

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        """Stream a control-plane-local file into the bench at ``workbench_path``.

        ``source_path`` need only exist on the control plane; the bytes travel
        as a chunked transfer (see ``repo2ree_protocol.workbench``)."""
        ...

    def delete_ree(self, workbench_id: str, ree_id: str) -> None:
        """Delete an REE and its directory from the store the workbench serves."""
        ...

    def is_connected(self, workbench_id: str) -> bool: ...

    def session_of(self, workbench_id: str) -> str | None:
        """The WorkbenchSession a command for ``workbench_id`` would be sent on now, if it is connected."""
        ...
