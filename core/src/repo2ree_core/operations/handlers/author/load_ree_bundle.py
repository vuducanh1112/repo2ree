from __future__ import annotations

import tempfile
from pathlib import Path

from repo2ree_core.bundle.restore import restore_ree_bundle
from repo2ree_core.execution.process import CancelCheck, format_command, run_streaming_process
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import safe_extract_zip, write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reproduction.acquire_source import build_acquire_sh
from repo2ree_core.reproduction.materialize_workspace import build_materialize_sh
from repo2ree_core.workspace.materialization import record_materialization
from repo2ree_protocol.command import LoadReeBundleArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import LoadReeBundleOutputs
from repo2ree_protocol.result import ActionResult


def handle_load_ree_bundle(
    args: LoadReeBundleArgs,
    *,
    layout: ReeLayout,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    store = ReeDirectory(layout)
    if store.manifest_exists() and store.read_ree().seal is not None:
        log("system", "error", "a sealed REE cannot load a bundle")
        return ActionResult.failed("precondition", "a sealed REE cannot load a bundle")
    staged = layout.upload_staging_file(args.upload_token)
    if not staged.exists():
        log("system", "error", f"staged bundle not found: {staged}")
        return ActionResult.failed("precondition", f"staged bundle not found: {staged}")

    log("system", "info", f"loading REE bundle {args.archive_name}")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            safe_extract_zip(staged, bundle_root)
            portable = staged
            if (bundle_root / "export.json").is_file() and (bundle_root / "ree.zip").is_file():
                portable = bundle_root / "ree.zip"
                bundle_root = bundle_root / "portable"
                safe_extract_zip(portable, bundle_root)
            loaded = restore_ree_bundle(
                layout,
                bundle_root=bundle_root,
                archive_path=portable,
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
    restored = _restored_files(layout, sealed=loaded.sealed)
    rebuilt = _rebuild_derived_trees(layout, restored_source=loaded.source_restored, log=log, is_canceled=is_canceled)
    _put_back(restored)
    if rebuilt is not None:
        return rebuilt

    return ActionResult(
        status="succeeded",
        exit_code=0,
        outputs=LoadReeBundleOutputs(archive_name=args.archive_name, loaded=loaded).model_dump(mode="json"),
    )


def _restored_files(layout: ReeLayout, *, sealed: bool) -> dict[Path, bytes | None]:
    paths = [layout.acquire_script, layout.materialize_script, *([layout.materialize_marker] if sealed else [])]
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def _put_back(restored: dict[Path, bytes | None]) -> None:
    for path, content in restored.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            write_atomic(path, content)


def _rebuild_derived_trees(
    layout: ReeLayout,
    *,
    restored_source: bool,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult | None:
    store = ReeDirectory(layout)
    if restored_source:
        write_atomic(layout.acquire_script, build_acquire_sh())
        failure = _run_script(layout.acquire_script, what="acquire", log=log, is_canceled=is_canceled)
        if failure is not None:
            return failure

    write_atomic(layout.materialize_script, build_materialize_sh())
    failure = _run_script(layout.materialize_script, what="materialize", log=log, is_canceled=is_canceled)
    if failure is not None:
        return failure
    source_receipt = store.read_ree().subject.receipts.acquire_source
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
