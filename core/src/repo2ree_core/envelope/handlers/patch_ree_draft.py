"""Handler for the patch_ree_draft operation.

Applies a partial patch to the reeDraft in /ree/.workspace.json.
Mirrors the host-side patch_ree_draft behaviour (field validation included).
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree import REE
from repo2ree_protocol.command import PatchReeDraftArgs
from repo2ree_protocol.result import ActionResult
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck

# Fields that callers may not patch (backend-managed).
_DRAFT_PATCH_FIELDS: frozenset[str] = frozenset(
    f
    for f in REE.model_fields
    if f
    not in {
        "dependency_level",
        "environment_level",
        "machine_level",
        "sealed_at",
        "seal_hash",
        "source_available",
        "source_acquired_by",
        "uploaded_archive",
        "source_snapshot_archive",
        "source_snapshot_captured_at",
        "downloadable_files",
    }
)


def handle_patch_ree_draft(
    args: PatchReeDraftArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "patch_ree_draft canceled before start")
        return ActionResult(status="canceled")

    unsupported = sorted(set(args.patch) - _DRAFT_PATCH_FIELDS)
    if unsupported:
        log("system", "error", f"patch contains backend-managed fields: {unsupported}")
        return ActionResult(status="failed", exit_code=1)

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        log("system", "error", "metadata not found — was init-ree run?")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", f"patch_ree_draft: {sorted(args.patch)}")
    try:
        metadata = store.read_metadata_json()
        ree = REE.from_metadata(metadata).apply_patch(args.patch)
        metadata["reeDraft"] = ree.model_dump(exclude_none=True)
        if ree.name:
            metadata["name"] = ree.name
        if ree.origin_url:
            metadata["externalRef"] = ree.origin_url
        source = metadata.get("source")
        if isinstance(source, dict) and ree.source_type:
            source["sourceType"] = ree.source_type
            metadata["source"] = source
        store.write_metadata_json(metadata)
    except Exception as exc:
        log("system", "error", f"patch_ree_draft failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    return ActionResult(status="succeeded", exit_code=0)
