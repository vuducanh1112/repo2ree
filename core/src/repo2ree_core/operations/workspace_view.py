"""The composed REE document: on-disk state read together with its evidence.

This is a read model, not storage. It sits in the application layer because it
joins three things that must not know about each other — the REE tree
(``ree``), the receipts and derived step states (``receipts``, ``ree_steps``),
and the draft manifest (``bundle.manifest``). Pushing it down into ``ree``
would make the persisted aggregate depend on the evidence stored inside it.

Consumed by the executor CLI's ``get-workspace``, which is what the API's REE
document is built from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from repo2ree_core.bundle.manifest import build_draft_manifest_payload
from repo2ree_core.evidence.receipts.consistency import build_author_receipt_set, build_consistency_report
from repo2ree_core.evidence.receipts.store import load_author_receipts
from repo2ree_core.evidence.steps import build_ree_step_states
from repo2ree_core.ree.workspace.views import layout_for, read_metadata, ree_files, workspace_files
from repo2ree_core.source_repo import derive_source_repo_metadata


def get_workspace(storage_root: Path, ree_id: str, *, include_content: bool = True) -> dict[str, Any]:
    metadata = read_metadata(storage_root, ree_id)
    intent = metadata.ree_intent
    session = metadata.ree_session
    detail: dict[str, Any] = metadata.model_dump()
    files = workspace_files(storage_root, ree_id, include_content=include_content)
    files_in_ree = ree_files(storage_root, ree_id, include_content=include_content)
    detail["files"] = files
    detail["ree_files"] = files_in_ree
    detail["draft_manifest"] = build_draft_manifest_payload(
        metadata,
        workspace_files=files,
        ree_files=files_in_ree,
    )
    detail["source_repo"] = derive_source_repo_metadata(intent, session, files).model_dump()
    # Live per-step staleness (recorded receipts vs. the current tree): saving
    # a script flips the derived state on the next fetch — no invalidation
    # events needed.
    layout = layout_for(storage_root, ree_id)
    consistency = build_consistency_report(layout, intent, session)
    detail["consistency"] = consistency.model_dump()
    detail["author_receipts"] = build_author_receipt_set(layout, intent, session).model_dump()
    # Operational overlay — done / ready / blocked per authoring step. Completion
    # is "a successful run is recorded" (the receipt-step keys), matching the
    # frontend badges and the scorecard; staleness stays on the consistency
    # report above. Evaluate records no receipt, so its report artifact is the
    # signal the receipt keys can't carry.
    completed_run_steps = set(load_author_receipts(layout))
    detail["ree_steps"] = [
        state.model_dump()
        for state in build_ree_step_states(
            intent,
            session,
            completed_run_steps=completed_run_steps,
            evaluate_report_present=(layout.artifacts / "reproducibility-report.json").is_file(),
        )
    ]
    return detail
