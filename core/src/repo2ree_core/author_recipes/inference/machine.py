"""What inference may learn about the machine an REE's scripts run on.

The engine stays pure: a check reads the machine through ``EngineProbe``, which the operations handler
supplies over the REE's script runner and tests supply as a fixed answer. The default probes nothing, and a
check reads that as unknown, never as absence.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.inference import ContainerEnginesProbe


@runtime_checkable
class EngineProbe(Protocol):
    def probe(self) -> ContainerEnginesProbe:
        """Which container engines a script run for this REE can use; probed at most once per request."""
        ...


class _NotProbed:
    def probe(self) -> ContainerEnginesProbe:
        return ContainerEnginesProbe(status="not_probed", detail="no engine probe was supplied")


class MachineInputs(BaseModel):
    """The machine facts on the decision context. Holds a probe object, so it is never serialized."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    engines: EngineProbe = Field(default_factory=_NotProbed)
