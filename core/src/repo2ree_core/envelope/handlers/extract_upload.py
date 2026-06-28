"""Handler for the extract_upload operation.

Reads /ree/upload-staging/<upload_token>.bin, extracts it into /ree/upstream/,
then removes the staging file.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from repo2ree_core.container.run_script import CancelCheck, LogSink
from repo2ree_core.storage.extract import safe_extract_tar, safe_extract_zip
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.storage.tree import copy_tree_contents
from repo2ree_protocol.command import ExtractUploadArgs
from repo2ree_protocol.result import ActionResult


def handle_extract_upload(
    args: ExtractUploadArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    if is_canceled():
        log("system", "warn", "extract_upload canceled before start")
        return ActionResult(status="canceled")

    layout = ReeLayout.in_workbench()
    staged = layout.upload_staging_file(args.upload_token)

    if not staged.exists():
        log("system", "error", f"staged archive not found: {staged}")
        return ActionResult(status="failed", exit_code=1)

    log("system", "info", f"extracting {args.archive_name} → {layout.upstream}")
    store = ReeStore(layout)
    store.upstream.clear()
    store.upstream.ensure_root()

    try:
        with tempfile.TemporaryDirectory() as tmp:
            extract_dir = Path(tmp)
            if args.archive_name.lower().endswith(".zip"):
                safe_extract_zip(staged, extract_dir)
            else:
                safe_extract_tar(staged, extract_dir)
            copy_tree_contents(extract_dir, layout.upstream)
    except Exception as exc:
        log("system", "error", f"extraction failed: {exc}")
        return ActionResult(status="failed", exit_code=1)

    staged.unlink(missing_ok=True)

    log("system", "info", "extract_upload succeeded")
    return ActionResult(status="succeeded", exit_code=0)
