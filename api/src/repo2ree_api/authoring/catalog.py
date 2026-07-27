"""What a client needs to know before authoring anything: the steps and the scripts.

Two deployment-static catalogs, published so a machine client can plan a
traversal cold instead of hardcoding what the frontend once hardcoded.

``listReeSteps`` is the static counterpart of ``getReeState``'s per-REE
``ree_steps`` overlay. Where the overlay says *what is done / ready / blocked for
this REE*, this publishes the structure the overlay refers to: the ordered steps,
their prerequisite edges, and — the HTTP binding core keeps out of itself — the
operationIds that advance each step. That join table (``_STEP_ACTIONS``) lives
here, one directory from the routes it names, because it must be updated
whenever a step gains or loses a route.

``listScriptTemplates`` serves the packaged starter templates for the REE-owned
scripts, so every client prefills from the same source
(``repo2ree_core.reserved_templates``) instead of keeping copies. The build and
activation templates are also seeded into a fresh REE's overlay; the
per-experiment templates cannot be (their paths only exist once an experiment is
named), so this catalog is how clients obtain them.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_core.ree_steps import ree_step_catalog
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    RESERVED_EXPERIMENT_SCRIPT_DIR,
)
from repo2ree_core.reserved_templates import (
    ScriptTemplate,
    activation_templates,
    build_templates,
    experiment_run_templates,
    verify_templates,
)

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

    Every catalog section lists these; exactly one entry per section carries
    ``is_default`` (for the seeded scripts it is the content a fresh REE starts
    with). The run-script sections currently carry a single ``docker`` variant
    each; the keys exist so further strategies can be added without changing
    the catalog shape.
    """

    key: str
    label: str
    description: str
    body: str
    is_default: bool


class BuildScriptTemplates(BaseModel):
    """The build-script templates and the reserved path they all belong at.

    One entry per standard runtime-packaging strategy; the default entry
    (``is_default``) is the content a fresh REE's build script is seeded with.
    """

    path: str
    templates: list[ScriptTemplateEntry]


class ActivationScriptTemplates(BaseModel):
    """The activation run-script templates and both reserved activation paths.

    The default template (``is_default``) is the content a fresh REE's
    activation script is seeded with. ``verify_script_path`` is where an
    activation verify script belongs when the author writes one; declaring it
    on the intent is an explicit act (a declared verify script must exist and
    pass).
    """

    run_script_path: str
    verify_script_path: str
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
    build: BuildScriptTemplates
    activation: ActivationScriptTemplates
    experiment: ExperimentScriptTemplates
    # Verify scripts share one contract across runnables (activation and
    # experiments), so their templates are catalog-wide.
    verify: list[ScriptTemplateEntry]


def _entries(templates: tuple[ScriptTemplate, ...]) -> list[ScriptTemplateEntry]:
    # The core catalogs order their entries default-first; publish that as an
    # explicit flag so clients don't have to know the positional convention.
    return [
        ScriptTemplateEntry(
            key=template.key,
            label=template.label,
            description=template.description,
            body=template.body,
            is_default=index == 0,
        )
        for index, template in enumerate(templates)
    ]


@script_templates_router.get(
    "/api/v1/script-templates",
    operation_id="listScriptTemplates",
    response_model=ScriptTemplateCatalog,
    responses=ERROR_RESPONSES,
)
def list_script_templates() -> ScriptTemplateCatalog:
    """Starter templates for the REE-owned scripts and where each belongs.

    Static per deployment. Each section marks its default entry with
    ``is_default``; the default build and activation templates are the same
    content a fresh REE is seeded with. The experiment templates are for
    scripts created on demand under the reserved experiments directory.
    """
    return ScriptTemplateCatalog(
        build=BuildScriptTemplates(
            path=RESERVED_BUILD_SCRIPT,
            templates=_entries(build_templates()),
        ),
        activation=ActivationScriptTemplates(
            run_script_path=RESERVED_ACTIVATION_SCRIPT,
            verify_script_path=RESERVED_ACTIVATION_VERIFY_SCRIPT,
            templates=_entries(activation_templates()),
        ),
        experiment=ExperimentScriptTemplates(
            run_script_path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh",
            verify_script_path_pattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh",
            templates=_entries(experiment_run_templates()),
        ),
        verify=_entries(verify_templates()),
    )
