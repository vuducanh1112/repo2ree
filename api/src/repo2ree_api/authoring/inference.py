"""The read-only script-inference route.

Binds the single synchronous ``generateScriptCandidates`` operation to the
workbench command of the same name. Inference scans the immutable upstream tree,
runs the versioned decision DAGs, and returns the full ``InferenceReport`` — it
persists nothing and writes no files. Turning a returned candidate into an
actual script stays on the existing ``writeReeFile`` (PUT .../files/content)
path; there is no apply or resolve endpoint here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from repo2ree_api.contracts import ERROR_RESPONSES
from repo2ree_api.workbench.commands import dispatch_or_fail, ree_command_span, require_handle
from repo2ree_core.author_recipes.inference.models import InferenceReport
from repo2ree_protocol.command import (
    GenerateScriptCandidatesArgs,
    GenerateScriptCandidatesCommand,
    ScriptTargetSelectorArg,
    TargetKind,
)

# ================================================
# Router
# ================================================


inference_router = APIRouter(tags=["files"])


# ================================================
# Data Models
# ================================================


# Its own model rather than the command's ``ScriptTargetSelectorArg``, because
# the class name and docstring are the schema name and description in the
# published contract — but the kind vocabulary comes from that arg's
# ``TargetKind``, so what a client may ask for and what the workbench accepts
# cannot drift apart. Keep maintenance notes like this one *out* of the
# docstring: it is published to every API consumer.
class ScriptTargetSelectorPayload(BaseModel):
    """One target a caller asks inference about: a kind, never a path.

    The workbench resolves the reserved path from the kind (and, for
    experiments, the reserved slug convention); a caller cannot redirect
    inference at an arbitrary workspace file.
    """

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None


class GenerateScriptCandidatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorPayload]


# ================================================
# Route Handlers
# ================================================


@inference_router.post(
    "/api/v1/rees/{ree_id}/script-inferences:generate",
    operation_id="generateScriptCandidates",
    response_model=InferenceReport,
    responses=ERROR_RESPONSES,
)
def generate_script_candidates_route(ree_id: str, payload: GenerateScriptCandidatesPayload) -> dict[str, Any]:
    """Synchronously generate candidate scripts for the requested targets.

    Read-only and always recomputed: every call rescans and re-runs the DAGs
    against current inputs, so it needs no idempotency key and returns the report
    directly rather than a background run.
    """
    handle = require_handle(ree_id)
    with ree_command_span("generate-script-candidates", ree_id):
        cmd = GenerateScriptCandidatesCommand(
            args=GenerateScriptCandidatesArgs(
                targets=[
                    ScriptTargetSelectorArg(kind=target.kind, experiment_name=target.experiment_name)
                    for target in payload.targets
                ]
            )
        )
        result = dispatch_or_fail(handle, cmd, "generate-script-candidates", "Workbench inference failed")
        return result.outputs
