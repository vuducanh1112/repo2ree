"""Authoring the workspace itself: read, write, and delete REE files.

The step graph never names these — writing the reserved build script is how the
``build`` step becomes runnable, not a step of its own — but every scripted step
passes through here, so they are their own module rather than an appendix to one
of them.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from repo2ree_api.contracts import ERROR_RESPONSES, FileMutationResponse, WorkspaceFileContentPayload
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_core.digests import digest_bytes
from repo2ree_protocol import DeleteFileCommand, WriteFileCommand
from repo2ree_protocol.command import DeleteFileArgs, WriteFileArgs

files_router = APIRouter(tags=["rees", "files"])


@files_router.get(
    "/api/v1/rees/{ree_id}/files/raw",
    operation_id="readReeFile",
    response_class=Response,
    responses={
        **ERROR_RESPONSES,
        200: {
            "description": "Raw workspace file bytes",
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
)
def get_workspace_file_raw_route(ree_id: str, path: str = Query(...)) -> Response:
    handle = require_handle(ree_id)
    try:
        content = workbench_manager.read_file_bytes(handle, path)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=content, media_type="application/octet-stream")


@files_router.put(
    "/api/v1/rees/{ree_id}/files/content",
    operation_id="writeReeFile",
    response_model=FileMutationResponse,
    responses=ERROR_RESPONSES,
)
def put_workspace_file_content_route(ree_id: str, payload: WorkspaceFileContentPayload) -> FileMutationResponse:
    handle = require_handle(ree_id)
    with ree_command_span("write-file", ree_id):
        # The if_match check rides inside the command so the workbench verifies
        # it under the same per-REE serialization as the write — an API-side
        # pre-read could pass and still lose to a concurrent writer.
        cmd = WriteFileCommand(
            args=WriteFileArgs(path=payload.path, content=payload.content, expected_etag=payload.if_match or "")
        )
        wb_result = dispatch_or_fail(handle, cmd, "write-file", "Workbench write_file failed")
        result = dict(wb_result.outputs or {})
        # The workbench validates a later ``if_match`` against
        # ``workspace_content_etag``, which digests the stored bytes the same
        # way — one shared helper so the compare cannot drift across processes.
        result["etag"] = digest_bytes(payload.content.encode())
        result.setdefault("updated_at", None)
        return FileMutationResponse.model_validate(result)


@files_router.delete(
    "/api/v1/rees/{ree_id}/files/content",
    operation_id="deleteReeFile",
    response_model=FileMutationResponse,
    responses=ERROR_RESPONSES,
)
def delete_workspace_file_content_route(
    ree_id: str,
    path: str = Query(...),
    if_match: str | None = Query(None),
) -> FileMutationResponse:
    handle = require_handle(ree_id)
    with ree_command_span("delete-file", ree_id):
        cmd = DeleteFileCommand(args=DeleteFileArgs(path=path, expected_etag=if_match or ""))
        wb_result = dispatch_or_fail(handle, cmd, "delete-file", "Workbench delete_file failed")
        return FileMutationResponse.model_validate(wb_result.outputs or {"deleted_at": None})
