"""Read-only routes for saved-script lint and contract checks on drafts."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.authoring.inference import ScriptTargetSelectorPayload
from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.contracts.runs import runs
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_protocol.command import LintScriptsArgs, LintScriptsCommand, ScriptTargetSelectorArg
from repo2ree_protocol.lint import LintReport, ScriptDeclarations
from repo2ree_protocol.queries import LintDraftQuery

lint_router = APIRouter(tags=["files"])


class LintScriptsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorPayload]


class LintScriptsResponse(BaseModel):
    """Reports for existing scripts and paths for requested scripts that are absent."""

    model_config = ConfigDict(extra="forbid")

    reports: list[LintReport] = Field(default_factory=list)
    missing_scripts: list[str] = Field(default_factory=list)


class ScriptDraftPayload(BaseModel):
    """Unsaved source and the declarations against which to check it."""

    model_config = ConfigDict(extra="forbid")

    target: ScriptTargetSelectorPayload
    source: str
    declarations: ScriptDeclarations = ScriptDeclarations()


@lint_router.post(
    "/api/v1/rees/{ree_id}/lint-scripts",
    operation_id="lintScripts",
    openapi_extra=runs("lint_scripts"),
    response_model=LintScriptsResponse,
    responses=ERROR_RESPONSES,
)
def lint_scripts_route(ree_id: str, payload: LintScriptsPayload) -> LintScriptsResponse:
    """Statically check persisted scripts on every available tier."""
    with author_api_action("lint_scripts", ree_id):
        return _lint(ree_id, payload)


def _lint(ree_id: str, payload: LintScriptsPayload) -> LintScriptsResponse:
    handle = require_handle(ree_id)
    with ree_command_span("lint-scripts", ree_id):
        cmd = LintScriptsCommand(
            args=LintScriptsArgs(
                targets=[
                    ScriptTargetSelectorArg(kind=target.kind, experiment_name=target.experiment_name)
                    for target in payload.targets
                ]
            )
        )
        result = dispatch_or_fail(handle, cmd, "lint-scripts", "Workbench lint failed")
        return LintScriptsResponse.model_validate(result.outputs)


@lint_router.post(
    "/api/v1/rees/{ree_id}/script-lints:draft",
    operation_id="checkScriptDraft",
    response_model=LintReport,
    responses=ERROR_RESPONSES,
)
def check_script_draft_route(ree_id: str, payload: ScriptDraftPayload) -> LintReport:
    """Run the checks that start no process against unsaved source, on the REE's workbench."""
    handle = require_handle(ree_id)
    query = LintDraftQuery(
        kind=payload.target.kind,
        experiment_name=payload.target.experiment_name,
        experiment_environment_path=payload.declarations.experiment_environment_path,
        source=payload.source,
    )
    try:
        return command_dispatcher.lint_draft(handle, query)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench draft check failed: {exc}") from exc
