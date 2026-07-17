"""The script-template catalog route.

Serves the packaged starter templates for the REE-owned scripts, so every
client — the frontend editors and pure-API agents alike — prefills from the
same single source (``repo2ree_core.reserved_templates``) instead of keeping
copies. The build and activation templates are also seeded into a fresh REE's
overlay; the per-experiment templates cannot be (their paths only exist once an
experiment is named), so this catalog is how clients obtain them.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from repo2ree_api.contracts import ERROR_RESPONSES
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

script_templates_router = APIRouter(tags=["files"])


class ScriptTemplateEntry(BaseModel):
    """One named starter-template variant for an REE-owned script.

    Every catalog section lists these; exactly one entry per section carries
    ``isDefault`` (for the seeded scripts it is the content a fresh REE starts
    with). The run-script sections currently carry a single ``docker`` variant
    each; the keys exist so further strategies can be added without changing
    the catalog shape.
    """

    key: str
    label: str
    description: str
    body: str
    isDefault: bool


class BuildScriptTemplates(BaseModel):
    """The build-script templates and the reserved path they all belong at.

    One entry per standard runtime-packaging strategy; the default entry
    (``isDefault``) is the content a fresh REE's build script is seeded with.
    """

    path: str
    templates: list[ScriptTemplateEntry]


class ActivationScriptTemplates(BaseModel):
    """The activation run-script templates and both reserved activation paths.

    The default template (``isDefault``) is the content a fresh REE's
    activation script is seeded with. ``verifyScriptPath`` is where an
    activation verify script belongs when the author writes one; declaring it
    on the intent is an explicit act (a declared verify script must exist and
    pass).
    """

    runScriptPath: str
    verifyScriptPath: str
    templates: list[ScriptTemplateEntry]


class ExperimentScriptTemplates(BaseModel):
    """Templates for per-experiment run scripts, plus the path convention they follow.

    The path patterns carry a ``{slug}`` placeholder: the experiment name with
    whitespace collapsed to hyphens. Naming an experiment on the intent settles
    its ``run_script`` to this convention server-side; the patterns are
    published so clients can show the destination before the intent round-trips.
    """

    runScriptPathPattern: str
    verifyScriptPathPattern: str
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
            isDefault=index == 0,
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
    ``isDefault``; the default build and activation templates are the same
    content a fresh REE is seeded with. The experiment templates are for
    scripts created on demand under the reserved experiments directory.
    """
    return ScriptTemplateCatalog(
        build=BuildScriptTemplates(
            path=RESERVED_BUILD_SCRIPT,
            templates=_entries(build_templates()),
        ),
        activation=ActivationScriptTemplates(
            runScriptPath=RESERVED_ACTIVATION_SCRIPT,
            verifyScriptPath=RESERVED_ACTIVATION_VERIFY_SCRIPT,
            templates=_entries(activation_templates()),
        ),
        experiment=ExperimentScriptTemplates(
            runScriptPathPattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh",
            verifyScriptPathPattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh",
            templates=_entries(experiment_run_templates()),
        ),
        verify=_entries(verify_templates()),
    )
