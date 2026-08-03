"""Author-controlled definition mutations for a portable REE."""

from __future__ import annotations

from fastapi import APIRouter

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    ReeDefinitionPatchPayload,
    ReeDefinitionReplacePayload,
    ReeDocument,
)
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_protocol import PatchReeDefinitionCommand
from repo2ree_protocol.command import PatchReeDefinitionArgs

definition_router = APIRouter(tags=["rees"])


@definition_router.patch(
    "/api/v1/rees/{ree_id}/definition",
    operation_id="patchReeDefinition",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def patch_ree_definition_route(ree_id: str, payload: ReeDefinitionPatchPayload) -> ReeDocument:
    handle = require_handle(ree_id)
    with ree_command_span("patch-definition", ree_id):
        command = PatchReeDefinitionCommand(
            args=PatchReeDefinitionArgs(
                patch=payload.definition_patch,
                expected_version=payload.expected_version or "",
            )
        )
        dispatch_or_fail(
            handle,
            command,
            "patch-definition",
            "Workbench patch_ree_definition failed",
        )
        return ReeDocument.model_validate(workbench_manager.get_ree_document(handle))


@definition_router.put(
    "/api/v1/rees/{ree_id}/definition",
    operation_id="replaceReeDefinition",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def replace_ree_definition_route(ree_id: str, payload: ReeDefinitionReplacePayload) -> ReeDocument:
    return patch_ree_definition_route(
        ree_id,
        ReeDefinitionPatchPayload(
            definition_patch=payload.definition.model_dump(mode="json"),
            expected_version=payload.expected_version,
        ),
    )
