"""The REE step catalog: the authoring step graph, published for machine clients.

The static counterpart of ``getReeState``'s per-REE ``ree_steps`` overlay. Where
the state overlay says *what is done / ready / blocked for this REE*, this
endpoint publishes the deployment-static structure the overlay refers to: the
ordered steps, their prerequisite edges, and — the HTTP binding core keeps out
of itself — the operationIds that advance each step. A client fetches it once to
render the process graph or plan a traversal, instead of hardcoding the step
shape the way each frontend previously did.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_core.ree_steps import ree_step_catalog

# ================================================
# Router
# ================================================


ree_steps_router = APIRouter(tags=["ree-steps"])


# ================================================
# Data models
# ================================================


class ReeStepCatalogEntry(BaseModel):
    """One authoring step: its structure (from core) plus the calls that run it."""

    model_config = ConfigDict(extra="forbid")

    key: str
    order: int
    label: str
    requires: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class ReeStepCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[ReeStepCatalogEntry] = Field(default_factory=list)


# The HTTP binding: which public operations advance each step. Lives in the API
# layer, not core — operationIds are a contract concern. A step may expose more
# than one call (an alternate path, or an init/commit pair); order is
# most-direct first.
_STEP_ACTIONS: dict[str, list[str]] = {
    "source": ["startSourceAcquisition", "initializeSourceUpload", "completeSourceUpload"],
    "metadata": ["patchReeIntent"],
    "hbom": ["startHbomGeneration", "patchReeIntent"],
    "evaluate": ["startEvaluate"],
    "build": ["startBuild"],
    "sbom": ["startSbomGeneration"],
    "crosscheck": ["startSbomCrossCheck"],
    "activation": ["startActivationTest"],
    "experiments": ["startExperiment"],
    "seal": ["sealRee"],
}


# ================================================
# Route handler
# ================================================


@ree_steps_router.get(
    "/api/v1/ree-steps",
    operation_id="listReeSteps",
    response_model=ReeStepCatalog,
    responses=ERROR_RESPONSES,
)
def list_ree_steps() -> ReeStepCatalog:
    """The static authoring steps: ordered, their prerequisite edges, and the
    operationIds that advance each. Deployment-static, so a client may cache it."""
    return ReeStepCatalog(
        steps=[
            ReeStepCatalogEntry(
                key=step.key,
                order=step.order,
                label=step.label,
                requires=step.requires,
                actions=_STEP_ACTIONS.get(step.key, []),
            )
            for step in ree_step_catalog()
        ]
    )
