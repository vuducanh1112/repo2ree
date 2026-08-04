"""The static REE authoring checklist and its prerequisite graph.

Not to be read as a sibling of :mod:`repo2ree_core.operations.steps`, which is
the machinery a step *handler* is assembled from. This is the graph those
handlers advance a client through — a navigation model over the persisted
record, with no execution in it.

The step list and its ``requires`` edges are the single declared source of the
authoring graph — the same steps the GUI renders as its process ring
(``REE_STEPS`` there), lifted out of the UI so every client reads the identical
structure instead of re-deriving it. Per-REE readiness and freshness live in
``ReeAudit``; this module deliberately owns no second lifecycle model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ================================================
# Static structure — the authoring step graph
# ================================================


class ReeStep(BaseModel):
    """One node of the authoring checklist: its position and prerequisites.

    Purely structural and deployment-static — the same for every REE. The
    concrete calls that advance a step (operationIds) are an HTTP concern and
    are joined on by whichever surface exposes the graph, not carried here.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    order: int
    label: str
    requires: list[str] = Field(default_factory=list)


# The authoring steps, in operator order. ``requires`` names the steps whose
# evidence must exist before this one can run — the hard edges the run handlers
# enforce (a build before its SBOM/activation; both an SBOM and an evaluate
# report before the cross-check). Steps without a hard edge (source, metadata,
# hbom, seal) carry none: they are gated by authoring, not by a prior run.
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
    """The static step catalog: the graph a client renders or plans against."""
    return list(REE_STEPS)
