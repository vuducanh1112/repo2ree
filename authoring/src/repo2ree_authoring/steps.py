from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReeStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    order: int
    label: str
    requires: list[str] = Field(default_factory=list)


REE_STEPS: tuple[ReeStep, ...] = (
    ReeStep(key="source", order=1, label="Source Acquisition"),
    ReeStep(key="metadata", order=2, label="Provide Metadata"),
    ReeStep(key="hbom", order=3, label="Hardware BOM"),
    ReeStep(key="evaluate", order=4, label="Reproducibility Readiness", requires=["source"]),
    ReeStep(key="build", order=5, label="Build Runtime", requires=["source"]),
    ReeStep(key="sbom", order=6, label="Generate SBOM", requires=["build"]),
    ReeStep(key="crosscheck", order=7, label="Cross-check SBOM", requires=["sbom", "evaluate"]),
    ReeStep(key="activation", order=8, label="Test Activation", requires=["build"]),
    ReeStep(key="experiments", order=9, label="Experiments", requires=["build"]),
    ReeStep(key="seal", order=10, label="Seal", requires=[]),
)


def ree_step_catalog() -> list[ReeStep]:
    return list(REE_STEPS)
