from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.workbench.commands import require_handle
from repo2ree_protocol.catalog import ReeStepKey, ReeStepState, ScriptTemplateCatalog

ree_steps_router = APIRouter(tags=["ree-steps"])


class ReeStepCatalogEntry(ReeStepState):
    actions: list[str] = Field(default_factory=list)


class ReeStepCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[ReeStepCatalogEntry] = Field(default_factory=list)
    next: ReeStepKey | None = None


STEP_ACTIONS_EXTENSION = "x-repo2ree-step-actions"

_STEP_ACTIONS: dict[ReeStepKey, list[str]] = {
    "acquire_source": ["acquireSource", "initializeSourceUpload", "completeSourceUpload"],
    "metadata": ["patchReeDefinition"],
    "observe_hardware": ["observeHardware", "patchReeDefinition"],
    "check_working_environment": ["writeScript", "patchReeDefinition", "checkWorkingEnvironment"],
    "evaluate_reproducibility": ["evaluateReproducibility"],
    "build_experiment_environment": ["buildExperimentEnvironment", "suggestScripts", "writeScript"],
    "generate_sbom": ["generateSbom"],
    "cross_check_sbom": ["crossCheckSbom"],
    "activate_experiment_environment": ["activateExperimentEnvironment"],
    "experiments": ["runExperiment", "patchReeDefinition", "suggestScripts", "writeScript"],
    "seal_ree": ["sealRee"],
}


@ree_steps_router.get(
    "/api/v1/rees/{ree_id}/ree-steps",
    operation_id="listReeSteps",
    response_model=ReeStepCatalog,
    responses=ERROR_RESPONSES,
    openapi_extra={STEP_ACTIONS_EXTENSION: _STEP_ACTIONS},
)
def list_ree_steps(ree_id: str) -> ReeStepCatalog:
    handle = require_handle(ree_id)
    try:
        steps = command_dispatcher.get_ree_state(handle).steps
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench step query failed: {exc}") from exc
    return ReeStepCatalog(
        steps=[ReeStepCatalogEntry(**step.model_dump(), actions=_STEP_ACTIONS[step.key]) for step in steps.steps],
        next=steps.next,
    )


script_templates_router = APIRouter(tags=["files"])


@script_templates_router.get(
    "/api/v1/rees/{ree_id}/script-templates",
    operation_id="listScriptTemplates",
    response_model=ScriptTemplateCatalog,
    responses=ERROR_RESPONSES,
)
def list_script_templates(ree_id: str) -> ScriptTemplateCatalog:
    handle = require_handle(ree_id)
    try:
        return command_dispatcher.list_script_templates(handle)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench template query failed: {exc}") from exc
