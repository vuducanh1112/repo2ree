"""Load a previously downloaded REE bundle into this (blank) workbench.

Reads /ree/upload-staging/<upload_token>.bin — a downloaded REE ZIP, sealed or
draft — and makes this REE be what the bundle records: the manifest, the frozen
snapshot, overlay, artifacts, results, and the author receipts that back them.
The untrusted upload bytes go through ``safe_extract_zip`` before anything is
read out of them, exactly as an uploaded source does.

The bundle publishes only the sources of truth, so the two derived trees are
rebuilt here rather than copied: the same ``acquire_source.sh`` a reproducer
runs extracts the restored snapshot into ``upstream/``, and
``materialize_workspace.sh`` merges it with the restored overlay. Both are the
shared muscles the authoring pipeline uses, driven directly so that loading is
one atomic command — the restored author receipts are evidence about the
author's runs and must not be overwritten by the loader's own.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.bundle.restore import BundleLoadOutputs, restore_ree_bundle
from repo2ree_core.execution.process import CancelCheck, format_command, run_streaming_process
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import safe_extract_zip, write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reproduction.acquire_source import build_acquire_sh
from repo2ree_core.reproduction.materialize_workspace import build_materialize_sh
from repo2ree_core.workspace.materialization import record_materialization
from repo2ree_protocol.command import LoadReeBundleArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class LoadReeBundleOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archive_name: str
    loaded: BundleLoadOutputs


def handle_load_ree_bundle(
    args: LoadReeBundleArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    staged = layout.upload_staging_file(args.upload_token)
    if not staged.exists():
        log("system", "error", f"staged bundle not found: {staged}")
        return ActionResult.failed("precondition", f"staged bundle not found: {staged}")

    log("system", "info", f"loading REE bundle {args.archive_name}")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            safe_extract_zip(staged, bundle_root)
            loaded = restore_ree_bundle(
                layout.root.parent,
                layout.root.name,
                bundle_root=bundle_root,
                archive_path=staged,
            )
    except Exception as exc:
        log("system", "error", f"bundle load failed: {exc}")
        return ActionResult.failed("validation", f"bundle load failed: {exc}")
    staged.unlink(missing_ok=True)

    log(
        "system",
        "info",
        f"restored {'sealed' if loaded.sealed else 'draft'} REE '{loaded.name}': "
        f"{loaded.overlay_files} overlay and {loaded.artifact_files} artifact files"
        + ("" if loaded.source_restored else " (bundle carried no source snapshot)"),
    )

    if is_canceled():
        return ActionResult(status="canceled")
    rebuilt = _rebuild_derived_trees(layout, restored_source=loaded.source_restored, log=log, is_canceled=is_canceled)
    if rebuilt is not None:
        return rebuilt

    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=LoadReeBundleOutputs(archive_name=args.archive_name, loaded=loaded).model_dump(mode="json"),
    )


def _rebuild_derived_trees(
    layout: ReeLayout,
    *,
    restored_source: bool,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult | None:
    """Rebuild ``upstream/`` and ``workspace/``. Returns non-None on failure."""
    store = ReeDirectory(layout)
    if restored_source:
        # Snapshot-only acquisition: the script extracts the restored snapshot
        # and never reaches for the origin, so loading stays offline.
        write_atomic(layout.acquire_script, build_acquire_sh())
        failure = _run_script(layout.acquire_script, what="acquire", log=log, is_canceled=is_canceled)
        if failure is not None:
            return failure

    write_atomic(layout.materialize_script, build_materialize_sh())
    failure = _run_script(layout.materialize_script, what="materialize", log=log, is_canceled=is_canceled)
    if failure is not None:
        return failure
    source_receipt = store.read_ree().subject.receipts.source
    record_materialization(
        layout,
        snapshot_digest=source_receipt.snapshot_digest if source_receipt else None,
        log=log,
    )
    return None


def _run_script(script: Path, *, what: str, log: LogSink, is_canceled: CancelCheck) -> ActionResult | None:
    command = ["sh", str(script)]
    log("system", "info", format_command(command))
    result = run_streaming_process(command, log=log, is_canceled=is_canceled)
    if result.canceled or is_canceled():
        log("system", "warn", f"load_ree_bundle canceled during {what}")
        return ActionResult(status="canceled")
    if result.returncode != 0:
        return ActionResult.failed(
            "execution",
            f"{what} script exited {result.returncode}",
            exit_code=result.returncode or 1,
        )
    return None
