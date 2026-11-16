"""What a client needs to know before authoring: where the REE stands on each step, and the scripts.

Both are what the REE's own command line says (``ree steps``, ``ree templates``),
read through the REE's workbench, so every client sees the same answer a person
at a terminal gets.

``listReeSteps`` adds the one thing the command line keeps out of itself: the HTTP
binding, the operationIds that advance each step. That join table
(``_STEP_ACTIONS``) lives here, one directory from the routes it names, because it
must be updated whenever a step gains or loses a route.

``listScriptTemplates`` serves the starter templates for the REE-owned scripts,
so every client prefills from the same source instead of keeping copies. The
build and activate experiment environment templates are also seeded into a fresh REE's overlay; the
per-experiment templates cannot be (their paths only exist once an experiment is
named), so this catalog is how clients obtain them.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.workbench.commands import require_handle
from repo2ree_protocol.catalog import ReeStepKey, ReeStepState, ScriptTemplateCatalog

# ================================================
# The step catalog
# ================================================


ree_steps_router = APIRouter(tags=["ree-steps"])


class ReeStepCatalogEntry(ReeStepState):
    """One authoring step as the REE stands on it, plus the operations that advance it."""

    actions: list[str] = Field(default_factory=list)


class ReeStepCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[ReeStepCatalogEntry] = Field(default_factory=list)
    next: ReeStepKey | None = None


# Where the contract carries ``_STEP_ACTIONS``, on ``listReeSteps``.
STEP_ACTIONS_EXTENSION = "x-repo2ree-step-actions"

# The HTTP binding: which public operations advance each step. Lives in the API
# layer, not core — operationIds are a contract concern. A step may expose more
# than one call (an alternate path, or an init/commit pair); order is
# most-direct first.
_STEP_ACTIONS: dict[ReeStepKey, list[str]] = {
    "source": ["startSourceAcquisition", "initializeSourceUpload", "completeSourceUpload"],
    "metadata": ["patchReeDefinition"],
    "hbom": ["startHbomGeneration", "patchReeDefinition"],
    "check_working_environment": ["writeReeFile", "patchReeDefinition", "startWorkingEnvironmentCheck"],
    "evaluate": ["startEvaluate"],
    "build_experiment_environment": ["startBuildExperimentEnvironment", "generateScriptCandidates", "writeReeFile"],
    "sbom": ["startSbomGeneration"],
    "crosscheck": ["startSbomCrossCheck"],
    "activation": ["startActivationTest"],
    "experiments": ["startExperiment", "patchReeDefinition", "generateScriptCandidates", "writeReeFile"],
    "seal": ["sealRee"],
}


@ree_steps_router.get(
    "/api/v1/rees/{ree_id}/ree-steps",
    operation_id="listReeSteps",
    response_model=ReeStepCatalog,
    responses=ERROR_RESPONSES,
    # The same join, in the contract, so a reader of the contract alone can tell which operations advance a step.
    openapi_extra={STEP_ACTIONS_EXTENSION: _STEP_ACTIONS},
)
def list_ree_steps(ree_id: str) -> ReeStepCatalog:
    """Each authoring step, ordered, with its prerequisites, where the REE stands on
    it (``complete``, ``ready`` or ``blocked``), and the operationIds that advance
    it; ``next`` is the step to do next."""
    handle = require_handle(ree_id)
    try:
        steps = command_dispatcher.get_ree_state(handle).steps
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench step query failed: {exc}") from exc
    return ReeStepCatalog(
        steps=[ReeStepCatalogEntry(**step.model_dump(), actions=_STEP_ACTIONS[step.key]) for step in steps.steps],
        next=steps.next,
    )


# ================================================
# The script-template catalog
# ================================================


script_templates_router = APIRouter(tags=["files"])


@script_templates_router.get(
    "/api/v1/rees/{ree_id}/script-templates",
    operation_id="listScriptTemplates",
    response_model=ScriptTemplateCatalog,
    responses=ERROR_RESPONSES,
)
def list_script_templates(ree_id: str) -> ScriptTemplateCatalog:
    """Starter templates for the REE-owned scripts and where each belongs.

    Static for the command line the REE's workbench runs. Each section marks the
    default entry for each environment with ``is_default``; the default build and
    activate experiment environment templates are the content a fresh REE in that
    environment is seeded with. The experiment templates are for scripts created on
    demand under the reserved experiments directory. For scripts fitted to the REE's
    own project, use ``generateScriptCandidates``.
    """
    handle = require_handle(ree_id)
    try:
        return command_dispatcher.list_script_templates(handle)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench template query failed: {exc}") from exc
