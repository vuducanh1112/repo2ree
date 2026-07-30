"""The composed REE document: on-disk state read together with its evidence.

This is a read model, not storage. It sits in the application layer because it
joins three things that must not know about each other — the REE tree
(``ree``), the receipts and derived step states (``receipts``, ``ree_steps``),
and the draft manifest (``bundle.manifest``). Pushing it down into ``ree``
would make the persisted aggregate depend on the evidence stored inside it.

Consumed by the executor CLI's ``get-workspace``, which is what the API's REE
document is built from. Because it crosses that boundary as JSON, the document
is a model rather than a dict: every part of it is already typed by whichever
layer produced it, and assembling them into an untyped bag would lose that
exactly where two processes have to agree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from repo2ree_core.bundle.manifest import build_draft_manifest_payload
from repo2ree_core.evidence.receipts.consistency import (
    AuthorReceiptSet,
    ConsistencyReport,
    build_author_receipt_set,
    build_consistency_report,
)
from repo2ree_core.evidence.receipts.store import load_author_receipts
from repo2ree_core.evidence.step_graph import ReeStepState, build_ree_step_states
from repo2ree_core.ree.workspace.inventory import ReeFile, WorkspaceFile
from repo2ree_core.ree.workspace.model import WorkspaceMetadata
from repo2ree_core.ree.workspace.views import layout_for, read_metadata, ree_files, workspace_files
from repo2ree_core.source_repo import SourceRepoMetadata, derive_source_repo_metadata


class WorkspaceDocument(WorkspaceMetadata):
    """The sidecar plus everything read alongside it in one fetch.

    Extends :class:`WorkspaceMetadata` because the document *is* the sidecar,
    observed together with what is currently true around it: the file
    inventories, the evidence derived from the receipts, and the manifest this
    REE would publish if it sealed now. Nothing here is stored — a second fetch
    recomputes all of it, which is what makes staleness visible without any
    invalidation event.
    """

    model_config = ConfigDict(extra="forbid")

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


def get_workspace(storage_root: Path, ree_id: str, *, include_content: bool = True) -> WorkspaceDocument:
    metadata = read_metadata(storage_root, ree_id)
    intent = metadata.ree_intent
    session = metadata.ree_session
    files = workspace_files(storage_root, ree_id, include_content=include_content)
    files_in_ree = ree_files(storage_root, ree_id, include_content=include_content)
    layout = layout_for(storage_root, ree_id)

    return WorkspaceDocument(
        **metadata.model_dump(),
        files=files,
        ree_files=files_in_ree,
        draft_manifest=build_draft_manifest_payload(
            metadata,
            workspace_files=files,
            ree_files=files_in_ree,
        ),
        source_repo=derive_source_repo_metadata(intent, session, files),
        # Live per-step staleness (recorded receipts vs. the current tree):
        # saving a script flips the derived state on the next fetch — no
        # invalidation events needed.
        consistency=build_consistency_report(layout, intent, session),
        author_receipts=build_author_receipt_set(layout, intent, session),
        # Operational overlay — done / ready / blocked per authoring step.
        # Completion is "a successful run is recorded" (the receipt-step keys),
        # matching the GUI badges and the scorecard; staleness stays on the
        # consistency report above. Evaluate records no receipt, so its report
        # artifact is the signal the receipt keys can't carry.
        ree_steps=build_ree_step_states(
            intent,
            session,
            completed_run_steps=set(load_author_receipts(layout)),
            evaluate_report_present=layout.reproducibility_report.is_file(),
        ),
    )
