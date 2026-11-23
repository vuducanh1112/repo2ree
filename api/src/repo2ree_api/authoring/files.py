from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from repo2ree_api.contracts import ERROR_RESPONSES, FileMutationResponse, WriteScriptPayload
from repo2ree_api.contracts.runs import runs
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_protocol.command import WriteScriptArgs, WriteScriptCommand
from repo2ree_protocol.outputs import NoOutputs
from repo2ree_ree.digest import digest_bytes

files_router = APIRouter(tags=["rees", "files"])


@files_router.get(
    "/api/v1/rees/{ree_id}/files/raw",
    operation_id="readReeFile",
    response_class=Response,
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "Raw REE file bytes",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
def get_ree_file_raw_route(ree_id: str, path: str = Query(...)) -> Response:
    with author_api_action("read_file", ree_id, path=path):
        handle = require_handle(ree_id)
        try:
            content = command_dispatcher.read_ree_file_bytes(handle, path)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(content=content, media_type="application/octet-stream")


@files_router.post(
    "/api/v1/rees/{ree_id}/write-script",
    operation_id="writeScript",
    openapi_extra=runs("write_script"),
    response_model=FileMutationResponse,
    responses=ERROR_RESPONSES,
)
def write_script_route(ree_id: str, payload: WriteScriptPayload) -> FileMutationResponse:
    with author_api_action("write_script", ree_id, path=payload.path):
        return _write_file(ree_id, payload)


def _write_file(ree_id: str, payload: WriteScriptPayload) -> FileMutationResponse:
    handle = require_handle(ree_id)
    with ree_command_span("write-file", ree_id):
        cmd = WriteScriptCommand(
            args=WriteScriptArgs(path=payload.path, content=payload.content, expected_etag=payload.if_match or "")
        )
        NoOutputs.model_validate(dispatch_or_fail(handle, cmd, "write-file", "Workbench write_script failed").outputs)
        return FileMutationResponse(etag=digest_bytes(payload.content.encode()))
