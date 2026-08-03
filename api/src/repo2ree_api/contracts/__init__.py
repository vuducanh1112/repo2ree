"""The published wire vocabulary: request payloads, responses, and the envelope.

Split by subject (``runs``, ``ree``, ``requests``, ``errors``) and re-exported
here, so route modules keep importing from one place — ``repo2ree_api.contracts``
— while the definitions stay grouped by what they describe.
"""

from repo2ree_api.contracts.errors import ERROR_RESPONSES, ErrorDetail, ErrorEnvelope
from repo2ree_api.contracts.ree import (
    DeleteReeResponse,
    FileMutationResponse,
    HealthResponse,
    ReeDocument,
    ReeIndexList,
    ReeList,
    ReeState,
    ReeSummary,
    ReprovisionResponse,
    UploadInitResponse,
    UploadStoredResponse,
    WorkbenchStatus,
)
from repo2ree_api.contracts.requests import (
    CreateRunPayload,
    ReeBundleLoadPayload,
    ReeCreatePayload,
    ReeDefinitionPatchPayload,
    ReeDefinitionReplacePayload,
    ReeSealPayload,
    SourceAcquirePayload,
    SourceUploadCompletePayload,
    StrictRequestModel,
    UploadInitPayload,
    WorkspaceFileContentPayload,
)
from repo2ree_api.contracts.runs import (
    CancelRunResponse,
    RunList,
    RunLogEntry,
    RunLogPage,
    RunObservation,
    RunOperation,
    RunStatus,
    RunSummary,
)

__all__ = [
    "ERROR_RESPONSES",
    "CancelRunResponse",
    "CreateRunPayload",
    "DeleteReeResponse",
    "ErrorDetail",
    "ErrorEnvelope",
    "FileMutationResponse",
    "HealthResponse",
    "ReeBundleLoadPayload",
    "ReeCreatePayload",
    "ReeDefinitionPatchPayload",
    "ReeDefinitionReplacePayload",
    "ReeDocument",
    "ReeIndexList",
    "ReeList",
    "ReeSealPayload",
    "ReeState",
    "ReeSummary",
    "ReprovisionResponse",
    "RunList",
    "RunLogEntry",
    "RunLogPage",
    "RunObservation",
    "RunOperation",
    "RunStatus",
    "RunSummary",
    "SourceAcquirePayload",
    "SourceUploadCompletePayload",
    "StrictRequestModel",
    "UploadInitPayload",
    "UploadInitResponse",
    "UploadStoredResponse",
    "WorkbenchStatus",
    "WorkspaceFileContentPayload",
]
