"""Handler for the extract_upload operation.

Reads /ree/upload-staging/<upload_token>.bin and turns it into the frozen
snapshot (/ree/snapshot.tar.gz), then removes the staging file. An upload has no
origin to re-fetch, so the snapshot *is* its canonical source: the unified
``acquire_source`` step then extracts that snapshot into /ree/upstream. The
untrusted upload bytes are run through ``safe_extract`` here — the one place the
path-traversal boundary lives — before being repacked into the trusted snapshot.

Effect only, for the same reason as ``snapshot_upstream``: the digest goes back
to the acquire lifecycle that asked for the freeze, and that lifecycle records it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from repo2ree_core.digests import Digest
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.persistence.files import pack_directory_tar_gz, safe_extract_tar, safe_extract_zip
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import ExtractUploadArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


def freeze_upload(layout: ReeLayout, *, upload_token: str, archive_name: str, log: LogSink) -> Digest:
    """Repack the staged upload into the snapshot archive and return its digest.

    The staging file is removed only once the snapshot is written, so a failure
    part-way leaves the upload where a retry can still find it.
    """
    staged = layout.upload_staging_file(upload_token)
    if not staged.is_file():
        raise FileNotFoundError(f"staged archive not found: {staged}")

    log("system", "info", f"packing {archive_name} → {layout.snapshot_archive.name}")
    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = Path(tmp)
        if archive_name.lower().endswith(".zip"):
            safe_extract_zip(staged, extract_dir)
        else:
            safe_extract_tar(staged, extract_dir)
        snapshot_digest = pack_directory_tar_gz(extract_dir, layout.snapshot_archive)

    staged.unlink(missing_ok=True)
    return snapshot_digest


def handle_extract_upload(
    args: ExtractUploadArgs,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    layout = ReeLayout.in_workbench()
    try:
        freeze_upload(layout, upload_token=args.upload_token, archive_name=args.archive_name, log=log)
    except FileNotFoundError as exc:
        log("system", "error", str(exc))
        return ActionResult.failed("precondition", str(exc))
    except Exception as exc:
        log("system", "error", f"upload ingest failed: {exc}")
        return ActionResult.failed("validation", f"upload ingest failed: {exc}")

    log("system", "info", "extract_upload succeeded")
    return ActionResult(status="succeeded", exit_code=0)
