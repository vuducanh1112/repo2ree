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
    experiment_run_template,
    reserved_script_template,
    verify_templates,
)

script_templates_router = APIRouter(tags=["files"])


class ScriptTemplate(BaseModel):
    """A starter template together with the workspace-relative path it belongs at."""

    path: str
    body: str


class VerifyTemplateEntry(BaseModel):
    """One prefilled verify-script template for a standard verification case."""

    key: str
    label: str
    description: str
    body: str


class ActivationScriptTemplates(BaseModel):
    """The activation run-script template and both reserved activation paths.

    ``verifyScriptPath`` is where an activation verify script belongs when the
    author writes one; declaring it on the intent is an explicit act (a
    declared verify script must exist and pass).
    """

    runScriptPath: str
    verifyScriptPath: str
    runScript: str


class ExperimentScriptTemplates(BaseModel):
    """Templates for per-experiment scripts, plus the path convention they follow.

    The path patterns carry a ``{slug}`` placeholder: the experiment name with
    whitespace collapsed to hyphens. Naming an experiment on the intent settles
    its ``run_script`` to this convention server-side; the patterns are
    published so clients can show the destination before the intent round-trips.
    """

    runScriptPathPattern: str
    verifyScriptPathPattern: str
    runScript: str


class ScriptTemplateCatalog(BaseModel):
    build: ScriptTemplate
    activation: ActivationScriptTemplates
    experiment: ExperimentScriptTemplates
    # Verify scripts share one contract across runnables (activation and
    # experiments), so their templates are catalog-wide. The first is the default.
    verify: list[VerifyTemplateEntry]


@script_templates_router.get(
    "/api/v1/script-templates",
    operation_id="listScriptTemplates",
    response_model=ScriptTemplateCatalog,
    responses=ERROR_RESPONSES,
)
def list_script_templates() -> ScriptTemplateCatalog:
    """Starter templates for the REE-owned scripts and where each belongs.

    Static per deployment. ``build`` and ``activation`` are the same content a
    fresh REE is seeded with; the experiment templates are for scripts created
    on demand under the reserved experiments directory. The first verify
    template is the default.
    """
    return ScriptTemplateCatalog(
        build=ScriptTemplate(
            path=RESERVED_BUILD_SCRIPT,
            body=reserved_script_template(RESERVED_BUILD_SCRIPT),
        ),
        activation=ActivationScriptTemplates(
            runScriptPath=RESERVED_ACTIVATION_SCRIPT,
            verifyScriptPath=RESERVED_ACTIVATION_VERIFY_SCRIPT,
            runScript=reserved_script_template(RESERVED_ACTIVATION_SCRIPT),
        ),
        experiment=ExperimentScriptTemplates(
            runScriptPathPattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.sh",
            verifyScriptPathPattern=f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{{slug}}.verify.sh",
            runScript=experiment_run_template(),
        ),
        verify=[
            VerifyTemplateEntry(
                key=template.key,
                label=template.label,
                description=template.description,
                body=template.body,
            )
            for template in verify_templates()
        ],
    )
