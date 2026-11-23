from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.inference import ContainerEnginesProbe, SlurmProbe


@runtime_checkable
class EngineProbe(Protocol):
    def probe(self) -> ContainerEnginesProbe: ...


@runtime_checkable
class SlurmProbeSource(Protocol):
    def probe(self) -> SlurmProbe: ...


class _NotProbed:
    def probe(self) -> ContainerEnginesProbe:
        return ContainerEnginesProbe(status="not_probed", detail="no engine probe was supplied")


class _SlurmNotProbed:
    def probe(self) -> SlurmProbe:
        return SlurmProbe(status="not_probed", detail="no Slurm probe was supplied")


class MachineInputs(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    engines: EngineProbe = Field(default_factory=_NotProbed)
    slurm: SlurmProbeSource = Field(default_factory=_SlurmNotProbed)
