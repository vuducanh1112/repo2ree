"""Read-only routes for saved-script lint and contract checks on drafts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from repo2ree_api.authoring.inference import ScriptTargetSelectorPayload
from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_core.author_recipes.lint import (
    CONTRACT_ONLY,
    LintReport,
    ScriptDeclarations,
    lint_script,
)
from repo2ree_core.author_recipes.targets import ScriptTargetSelector, resolve_target
from repo2ree_protocol.command import LintScriptsArgs, LintScriptsCommand, ScriptTargetSelectorArg

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
    "/api/v1/rees/{ree_id}/script-lints:run",
    operation_id="lintReeScripts",
    response_model=LintScriptsResponse,
    responses=ERROR_RESPONSES,
)
def lint_ree_scripts_route(ree_id: str, payload: LintScriptsPayload) -> dict[str, Any]:
    """Statically check persisted scripts on every available tier."""
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
        return result.outputs


@lint_router.post(
    "/api/v1/script-lints:draft",
    operation_id="checkScriptDraft",
    response_model=LintReport,
    responses=ERROR_RESPONSES,
)
def check_script_draft_route(payload: ScriptDraftPayload) -> LintReport:
    """Run process-free contract checks against unsaved source."""
    try:
        target = resolve_target(
            ScriptTargetSelector(
                kind=payload.target.kind,
                experiment_name=payload.target.experiment_name,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return lint_script(target, payload.source, declarations=payload.declarations, tiers=CONTRACT_ONLY)
