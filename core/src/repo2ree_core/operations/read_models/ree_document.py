"""The composed REE document: on-disk state read together with its evidence.

This is a read model, not storage. It sits in the application layer because it
joins three things that must not know about each other — the REE tree
(``ree``), the receipts and derived step states (``receipts``, ``ree_steps``),
and the draft manifest (``bundle.manifest``). Pushing it down into ``ree``
would make the persisted aggregate depend on the evidence stored inside it.

Consumed by the executor CLI's ``get-ree-document``, which is what the API's REE
document is built from. Because it crosses that boundary as JSON, the document
is a model rather than a dict: every part of it is already typed by whichever
layer produced it, and assembling them into an untyped bag would lose that
exactly where two processes have to agree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.bundle.manifest import build_draft_manifest_payload
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.evidence.consistency import (
    AuthorReceiptSet,
    ConsistencyReport,
    build_author_receipt_set,
    build_consistency_report,
)
from repo2ree_core.evidence.step_graph import ReeStepState, build_ree_step_states
from repo2ree_core.operations.read_models.files import (
    ReeFile,
    WorkspaceFile,
    list_ree_files,
    list_workspace_files,
)
from repo2ree_core.persistence.receipts import load_author_receipts
from repo2ree_core.persistence.repository import directory_for, layout_for, load_ree
from repo2ree_core.persistence.sidecar import ReeStatus
from repo2ree_core.source_repo import SourceRepoMetadata, derive_source_repo_metadata


class ReeDocument(BaseModel):
    """Application read model composed from a sidecar and current REE facts."""

    model_config = ConfigDict(extra="forbid")

    ree_id: str
    external_ref: str | None = None
    name: str
    status: ReeStatus = "draft"
    created_at: str
    updated_at: str
    ree_intent: ReeIntent = Field(default_factory=ReeIntent)
    ree_state: ReeLifecycleState = Field(default_factory=ReeLifecycleState)
    files: list[WorkspaceFile] = Field(default_factory=list)
    ree_files: list[ReeFile] = Field(default_factory=list)
    # A projection of the *would-be* manifest, whose source of truth is the
    # sealed sidecar; it stays a payload dict here rather than gaining a second,
    # competing schema for the same document.
    draft_manifest: dict[str, Any] = Field(default_factory=dict)
    source_repo: SourceRepoMetadata | None = None
    consistency: ConsistencyReport = Field(default_factory=ConsistencyReport)
    author_receipts: AuthorReceiptSet = Field(default_factory=AuthorReceiptSet)
    ree_steps: list[ReeStepState] = Field(default_factory=list)


def get_ree_document(storage_root: Path, ree_id: str, *, include_content: bool = True) -> ReeDocument:
    layout = layout_for(storage_root, ree_id)
    directory = directory_for(storage_root, ree_id)
    if not directory.sidecar_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    sidecar = directory.read_sidecar()
    ree = load_ree(layout, directory, sidecar=sidecar)
    intent = ree.authored.intent
    state = ree.evidence.state
    files = list_workspace_files(storage_root, ree_id, include_content=include_content)
    files_in_ree = list_ree_files(storage_root, ree_id, include_content=include_content)

    return ReeDocument(
        **sidecar.model_dump(),
        files=files,
        ree_files=files_in_ree,
        draft_manifest=build_draft_manifest_payload(
            sidecar,
            workspace_files=files,
            ree_files=files_in_ree,
        ),
        source_repo=derive_source_repo_metadata(intent, state, files),
        # Live per-step staleness (recorded receipts vs. the current tree):
        # saving a script flips the derived state on the next fetch — no
        # invalidation events needed.
        consistency=build_consistency_report(layout, intent, state),
        author_receipts=build_author_receipt_set(layout, intent, state),
        # Operational overlay — done / ready / blocked per authoring step.
        # Completion is "a successful run is recorded" (the receipt-step keys),
        # matching the GUI badges and the scorecard; staleness stays on the
        # consistency report above. Evaluate records no receipt, so its report
        # artifact is the signal the receipt keys can't carry.
        ree_steps=build_ree_step_states(
            intent,
            state,
            completed_run_steps=set(load_author_receipts(layout)),
            evaluate_report_present=layout.reproducibility_report.is_file(),
        ),
    )
