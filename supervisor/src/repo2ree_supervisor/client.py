"""The control plane's client for a workbench agent.

``AgentClient`` is the seam the manager depends on. The sole production
implementation is ``WsAgentClient`` (see ``ws.py``), which drives an agent that
dialed the control plane and holds one outbound WebSocket — the agent never
listens, so it works from inside clusters and NATed networks that only permit
egress. The manager is transport-agnostic behind this Protocol.

Streaming calls yield typed ``AgentFrame`` records; request/response calls
return plain values and raise ``WorkbenchUnavailableError`` when the agent
reports the backend is gone.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.agent import AgentFrame, ErrorFrame, UnavailableFrame, WorkbenchLocation


class WorkbenchUnavailableError(RuntimeError):
    """Raised when the agent reports the workbench backend is gone or stopping."""


def raise_for_terminal_error(frame: AgentFrame) -> None:
    """Translate a terminal error frame into the caller-facing exception.

    The two failure frames mean different things to the control plane: an
    ``UnavailableFrame`` is the backend being gone (a 503-shaped, retryable
    condition) while an ``ErrorFrame`` is an operation failure. Both the manager
    and ``WsAgentClient`` map them the same way, so the mapping lives here."""
    if isinstance(frame, UnavailableFrame):
        raise WorkbenchUnavailableError(frame.detail)
    if isinstance(frame, ErrorFrame):
        raise RuntimeError(frame.detail)


class AgentClient(Protocol):
    """The verbs the control plane needs to place and drive a workbench.

    Every verb takes an ``agent_id`` to target a specific agent (placement
    affinity): a workbench is pinned to the agent that provisioned it, so all
    later ops must reach that same agent. An empty ``agent_id`` means "any
    connected agent" — the single-agent / legacy path.
    """

    def resolve_agent(self, agent_id: str) -> str:
        """Resolve a placement request to the concrete agent that will serve it.

        Provision calls this to pin the REE to the agent it actually lands on,
        rather than to an empty "any agent" token that later ops can't honour once
        more than one agent is connected. Raises ``WorkbenchUnavailableError`` when
        no matching agent is connected."""
        ...

    def provision(self, agent_id: str, ree_id: str, image: str) -> Iterator[AgentFrame]: ...

    def reprovision(
        self, agent_id: str, ree_id: str, location: WorkbenchLocation, image: str
    ) -> Iterator[AgentFrame]: ...

    def remove(self, agent_id: str, ree_id: str, location: WorkbenchLocation) -> None: ...

    def is_running(self, agent_id: str, container_name: str) -> bool: ...

    def exec_simple(self, agent_id: str, container_name: str, argv: list[str], timeout: int = 60) -> None: ...

    def exec_query(self, agent_id: str, container_name: str, argv: list[str], timeout: int = 30) -> bytes: ...

    def exec_query_stream(
        self, agent_id: str, container_name: str, argv: list[str], timeout: int = 30
    ) -> Iterator[bytes]: ...

    def exec_action(
        self, agent_id: str, container_name: str, cmd_json: str, run_id: str, env: dict[str, str]
    ) -> Iterator[AgentFrame]: ...

    def copy_in(self, agent_id: str, container_name: str, source_path: str, container_path: str) -> None:
        """Stream a control-plane-local file into the container at ``container_path``.

        ``source_path`` need only exist on the control plane; the bytes travel
        as a chunked transfer (see ``repo2ree_protocol.agent``)."""
        ...
