from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.contracts.runs import runs
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_protocol.command import (
    ScriptTargetSelectorArg,
    SuggestScriptsArgs,
    SuggestScriptsCommand,
)
from repo2ree_protocol.inference import InferenceReport

inference_router = APIRouter(tags=["files"])


class ScriptTargetSelectorPayload(ScriptTargetSelectorArg):
    pass


class SuggestScriptsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorPayload]


@inference_router.post(
    "/api/v1/rees/{ree_id}/suggest-scripts",
    operation_id="suggestScripts",
    openapi_extra=runs("suggest_scripts"),
    response_model=InferenceReport,
    responses=ERROR_RESPONSES,
)
def suggest_scripts_route(ree_id: str, payload: SuggestScriptsPayload) -> InferenceReport:
    with author_api_action("suggest_scripts", ree_id):
        return _suggest(ree_id, payload)


def _suggest(ree_id: str, payload: SuggestScriptsPayload) -> InferenceReport:
    handle = require_handle(ree_id)
    with ree_command_span("generate-script-candidates", ree_id):
        cmd = SuggestScriptsCommand(
            args=SuggestScriptsArgs(
                targets=[
                    ScriptTargetSelectorArg(kind=target.kind, experiment_name=target.experiment_name)
                    for target in payload.targets
                ]
            )
        )
        result = dispatch_or_fail(handle, cmd, "generate-script-candidates", "Workbench inference failed")
        return InferenceReport.model_validate(result.outputs)
