"""The substrate-runtime seam: the verbs a workbench runtime must provide.

The agent control connection translates wire requests into
these verbs and streams the frames back. Everything substrate-specific
(containers, volumes, daemons, schedulers) lives behind this Protocol;
``DockerRuntime`` is the only implementation today, with cloud/HPC runtimes
as the intended future ones.

Benches are addressed exclusively by ``WorkbenchRef``: the runtime mints one
at provision time and every later verb receives it back verbatim. Its token is
the minting runtime's private vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.agent import AgentFrame, WorkbenchRef, WorkbenchSpec


class WorkbenchGoneError(RuntimeError):
    """The workbench backend is gone or stopping (a request/response call)."""


class WorkbenchRuntime(Protocol):
    """The verbs the agent needs to place and drive a workbench on its host.

    Streaming verbs yield ``AgentFrame`` records ending in a terminal frame;
    request/response verbs return plain values and raise ``WorkbenchGoneError`` when
    the failure means the bench is gone rather than the operation failed.
    """

    runtime_name: str

    def provision(self, ree_id: str, spec: WorkbenchSpec) -> Iterator[AgentFrame]:
        """Create a bench for ``ree_id``; ends with a workbench-ref frame."""
        ...

    def reprovision(self, ref: WorkbenchRef, spec: WorkbenchSpec) -> Iterator[AgentFrame]:
        """Replace the bench, keeping its backing storage; ends with a fresh
        workbench-ref frame."""
        ...

    def remove(self, ref: WorkbenchRef) -> None:
        """Tear down the bench and its backing storage (best-effort)."""
        ...

    def is_running(self, ref: WorkbenchRef) -> bool: ...

    def exec_action(self, ref: WorkbenchRef, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[AgentFrame]:
        """Run a typed Command through the bench's executor; ends with a ``result`` frame."""
        ...

    def exec_simple(self, ref: WorkbenchRef, argv: list[str], timeout: int = 60) -> None:
        """Run an executor subcommand (``argv`` excludes the executor binary),
        discarding output."""
        ...

    def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        """Run an executor subcommand, streaming its stdout."""
        ...

    def cancel_run(self, ref: WorkbenchRef, run_id: str) -> None: ...

    def copy_in(self, ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        """Land an agent-host file at ``workbench_path`` in the bench."""
        ...
