"""The substrate-runtime seam: the verbs a workbench runtime must provide.

The agent is a frame ferry — ``control_link`` translates wire requests into
these verbs and streams the frames back. Everything substrate-specific
(containers, volumes, daemons, schedulers) lives behind this Protocol;
``DockerRuntime`` is the only implementation today, with cloud/HPC runtimes
as the intended future ones.

Benches are addressed exclusively by ``WorkbenchLocation``: the runtime mints
one at provision time and every later verb receives it back verbatim. Its
fields are the minting runtime's private vocabulary — nothing outside the
runtime may interpret them, or the substrate leaks into the control plane.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.agent import AgentFrame, WorkbenchLocation


class WorkbenchGoneError(RuntimeError):
    """The workbench backend is gone or stopping (a request/response call)."""


class WorkbenchRuntime(Protocol):
    """The verbs the agent needs to place and drive a workbench on its host.

    Streaming verbs yield ``AgentFrame`` records ending in a terminal frame;
    request/response verbs return plain values and raise ``WorkbenchGoneError`` when
    the failure means the bench is gone rather than the operation failed.
    """

    def provision(self, ree_id: str, image: str) -> Iterator[AgentFrame]:
        """Create a bench for ``ree_id`` from ``image``; ends with a ``location`` frame."""
        ...

    def reprovision(self, ree_id: str, location: WorkbenchLocation, image: str) -> Iterator[AgentFrame]:
        """Replace the bench, keeping its backing storage; ends with a fresh
        ``location`` frame (the replacement may change how the bench is driven,
        e.g. its executor entry point)."""
        ...

    def remove(self, ree_id: str, location: WorkbenchLocation) -> None:
        """Tear down the bench and its backing storage (best-effort)."""
        ...

    def is_running(self, location: WorkbenchLocation) -> bool: ...

    def exec_action(
        self, location: WorkbenchLocation, cmd_json: str, run_id: str, env: dict[str, str]
    ) -> Iterator[AgentFrame]:
        """Run a typed Command through the bench's executor; ends with a ``result`` frame."""
        ...

    def exec_simple(self, location: WorkbenchLocation, argv: list[str], timeout: int = 60) -> None:
        """Run an executor subcommand (``argv`` excludes the executor binary),
        discarding output."""
        ...

    def exec_query_stream(self, location: WorkbenchLocation, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        """Run an executor subcommand, streaming its stdout."""
        ...

    def cancel_run(self, location: WorkbenchLocation, run_id: str) -> None: ...

    def copy_in(self, location: WorkbenchLocation, source_path: str, container_path: str) -> None:
        """Land a file that exists on the agent host at ``container_path`` in the bench."""
        ...
