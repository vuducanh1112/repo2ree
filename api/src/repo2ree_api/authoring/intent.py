"""The declaring steps: what the author asserts about the REE.

Metadata, the hardware BOM's declaration, the runtime artifact binding, and the
named experiments all land on one typed document — the ``ReeIntent`` — so they
are one pair of routes rather than a route per field. The steps they advance
(``metadata``, and the declaration half of ``hbom`` and ``experiments``) are the
ones the step graph gates on authoring rather than on a prior run.
"""

from __future__ import annotations

from fastapi import APIRouter

from repo2ree_api.contracts import (
    ERROR_RESPONSES,
    ReeDocument,
    ReeIntentPatchPayload,
    ReeIntentReplacePayload,
)
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_protocol import PatchReeIntentCommand
from repo2ree_protocol.command import PatchReeIntentArgs

intent_router = APIRouter(tags=["rees"])


@intent_router.patch(
    "/api/v1/rees/{ree_id}/intent",
    operation_id="patchReeIntent",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def patch_ree_intent_route(ree_id: str, payload: ReeIntentPatchPayload) -> ReeDocument:
    handle = require_handle(ree_id)
    with ree_command_span("patch-intent", ree_id):
        cmd = PatchReeIntentCommand(
            args=PatchReeIntentArgs(
                patch=payload.ree_intent_patch.model_dump(mode="json", exclude_unset=True),
                expected_version=payload.expected_version or "",
            )
        )
        dispatch_or_fail(handle, cmd, "patch-intent", "Workbench patch_ree_intent failed")
        return ReeDocument.model_validate(workbench_manager.get_ree_document(handle))


@intent_router.put(
    "/api/v1/rees/{ree_id}/intent",
    operation_id="replaceReeIntent",
    response_model=ReeDocument,
    responses=ERROR_RESPONSES,
)
def replace_ree_intent_route(ree_id: str, payload: ReeIntentReplacePayload) -> ReeDocument:
    """Atomically replace the complete typed authoring intent.

    Delegating to the patch route is a true replace only because the patch is
    re-validated from a full model_dump() — every ReeIntent field (defaults
    included) counts as explicitly set, so the patch dispatch's exclude_unset
    keeps them all and apply_patch overwrites each top-level key. Guarded by
    test_replace_intent_resets_fields_omitted_from_the_new_intent.
    """
    return patch_ree_intent_route(
        ree_id,
        ReeIntentPatchPayload(
            ree_intent_patch=ReeIntent.model_validate(payload.ree_intent.model_dump(mode="json")),
            expected_version=payload.expected_version,
        ),
    )
