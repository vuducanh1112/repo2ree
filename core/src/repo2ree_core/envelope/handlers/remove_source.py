"""Handler for the remove_source operation.

Clears upstream/, overlay/, workspace/ and snapshot.tar.gz, then resets
source fields in /ree/.workspace.json back to draft state.
Mirrors the host-side remove_source behaviour.
"""

from __future__ import annotations

from repo2ree_core.container.run_script import LogSink
from repo2ree_core.domain.ree import REE
from repo2ree_core.envelope.result import ActionResult
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.working_environment.base import CancelCheck


def handle_remove_source(
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "remove_source canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    store = ReeStore(layout)

    if not store.metadata_exists():
        log("system", "error", "metadata not found — was init-ree run?")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "remove_source: clearing content and resetting metadata")
    try:
        # Clear all content directories and snapshot archive.
        for subtree in (store.upstream, store.overlay, store.workspace):
            subtree.clear()
            subtree.ensure_root()
        if layout.snapshot_archive.exists():
            layout.snapshot_archive.unlink()

        # Reset metadata to draft state.
        metadata = store.read_metadata_json()
        cleared_ree = (
            REE.from_metadata(metadata)
            .with_source(None)
            .model_copy(
                update={
                    "origin_url": "",
                    "source_type": "",
                    "runtime": "",
                    "build_runtime_script": "",
                    "activation_script": "",
                    "sbom": "",
                    "source_included": False,
                    "runtime_included": False,
                    "dependency_level": 0,
                    "environment_level": 0,
                    "machine_level": 0,
                    "detected_dependencies": None,
                }
            )
        )
        metadata["status"] = "draft"
        metadata["externalRef"] = None
        metadata["source"] = None
        metadata["reeDraft"] = cleared_ree.model_dump(exclude_none=True)
        store.write_metadata_json(metadata)
    except Exception as exc:
        log("system", "error", f"remove_source failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", "remove_source succeeded")
    return ActionResult(status="succeeded", exit_code=0)
