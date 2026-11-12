"""What a client needs to know before authoring anything: the steps and the scripts.

Two deployment-static catalogs, published so a machine client can plan a
traversal cold instead of hardcoding what the GUI once hardcoded.

``listReeSteps`` is the static counterpart of ``getReeState``'s per-REE
``ree_steps`` overlay. Where the overlay says *what is done / ready / blocked for
this REE*, this publishes the structure the overlay refers to: the ordered steps,
their prerequisite edges, and — the HTTP binding core keeps out of itself — the
operationIds that advance each step. That join table (``_STEP_ACTIONS``) lives
here, one directory from the routes it names, because it must be updated
whenever a step gains or loses a route.

``listScriptTemplates`` serves the packaged starter templates for the REE-owned
scripts, so every client prefills from the same source
(``repo2ree_authoring.templates``) instead of keeping copies. The build and
activate experiment environment templates are also seeded into a fresh REE's overlay; the
per-experiment templates cannot be (their paths only exist once an experiment is
named), so this catalog is how clients obtain them.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_authoring.steps import ree_step_catalog
from repo2ree_authoring.templates import (
    ScriptTemplate,
    activate_experiment_environment_templates,
    build_templates,
    experiment_run_templates,
    verify_templates,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
)
from repo2ree_ree.workbench_environment import EnvironmentBackend

# ================================================
# The step catalog
# ================================================


ree_steps_router = APIRouter(tags=["ree-steps"])


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
    "metadata": ["patchReeDefinition"],
    "hbom": ["startHbomGeneration", "patchReeDefinition"],
    "evaluate": ["startEvaluate"],
    "build_experiment_environment": ["startBuildExperimentEnvironment", "generateScriptCandidates", "writeReeFile"],
    "sbom": ["startSbomGeneration"],
    "crosscheck": ["startSbomCrossCheck"],
    "activation": ["startActivationTest"],
    "experiments": ["startExperiment", "patchReeDefinition", "generateScriptCandidates", "writeReeFile"],
    "seal": ["sealRee"],
}


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


# ================================================
# The script-template catalog
# ================================================


script_templates_router = APIRouter(tags=["files"])


class ScriptTemplateEntry(BaseModel):
    """One named starter-template variant for an REE-owned script.

    Every catalog section lists these; one entry per environment carries
    ``is_default`` (for the seeded scripts it is the content a fresh REE in that
    environment starts with). ``workbench_environment`` is the REE workbench environment kind a
    variant suits, or null for one that suits any.
    """

    key: str
    label: str
    description: str
    body: str
    is_default: bool
    workbench_environment: EnvironmentBackend | None = None


class BuildExperimentEnvironmentScriptTemplates(BaseModel):
    """The build-script templates and the reserved path they all belong at.

    One entry per standard runtime-packaging strategy; the default entry for an
    environment (``is_default``) is the content a fresh REE's build script there is
    seeded with.
    """

    path: str
    templates: list[ScriptTemplateEntry]


class ActivateExperimentEnvironmentScriptTemplates(BaseModel):
    """The activate experiment environment templates and the reserved path they all belong at."""

    path: str
    templates: list[ScriptTemplateEntry]


class ExperimentScriptTemplates(BaseModel):
    """Templates for per-experiment run scripts, plus the path convention they follow.

    The path patterns carry a ``{slug}`` placeholder: the experiment name with
    whitespace collapsed to hyphens. Naming an experiment on the intent settles
    its ``run_script`` to this convention server-side; the patterns are
    published so clients can show the destination before the intent round-trips.
    """

    run_script_path_pattern: str
    verify_script_path_pattern: str
    templates: list[ScriptTemplateEntry]


class ScriptTemplateCatalog(BaseModel):
    build_experiment_environment: BuildExperimentEnvironmentScriptTemplates
    activate_experiment_environment: ActivateExperimentEnvironmentScriptTemplates
    experiment: ExperimentScriptTemplates
    # Verify scripts are shared by every experiment, so their templates are catalog-wide.
    verify: list[ScriptTemplateEntry]


def _entries(templates: tuple[ScriptTemplate, ...]) -> list[ScriptTemplateEntry]:
    # The core catalogs order each environment's entries default-first; publish that as
    # an explicit flag so clients don't have to know the positional convention.
    defaults = {template.workbench_environment: template for template in reversed(templates)}
    return [
        ScriptTemplateEntry(
            key=template.key,
            label=template.label,
            description=template.description,
            body=template.body,
            is_default=defaults[template.workbench_environment] is template,
            workbench_environment=template.workbench_environment,
        )
        for template in templates
    ]


@script_templates_router.get(
    "/api/v1/script-templates",
    operation_id="listScriptTemplates",
    response_model=ScriptTemplateCatalog,
    responses=ERROR_RESPONSES,
)
def list_script_templates() -> ScriptTemplateCatalog:
    """Starter templates for the REE-owned scripts and where each belongs.

    Static per deployment. Each section marks the default entry for each
    environment with ``is_default``; the default build and activate experiment environment templates
    are the content a fresh REE in that environment is seeded with. The experiment
    templates are for scripts created on demand under the reserved experiments
    directory. For scripts fitted to the REE's own project, use
    ``generateScriptCandidates``.
    """
    return ScriptTemplateCatalog(
        build_experiment_environment=BuildExperimentEnvironmentScriptTemplates(
            path=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
            templates=_entries(build_templates()),
        ),
        activate_experiment_environment=ActivateExperimentEnvironmentScriptTemplates(
            path=RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
            templates=_entries(activate_experiment_environment_templates()),
        ),
        experiment=ExperimentScriptTemplates(
            run_script_path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh",
            verify_script_path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh",
            templates=_entries(experiment_run_templates()),
        ),
        verify=_entries(verify_templates()),
    )
