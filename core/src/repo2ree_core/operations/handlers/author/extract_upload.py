from __future__ import annotations

import tempfile
from pathlib import Path

from repo2ree_core.persistence.files import pack_directory_tar_gz, safe_extract_tar, safe_extract_zip
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.frames import LogSink
from repo2ree_ree.digest import Digest


def freeze_upload(layout: ReeLayout, *, upload_token: str, archive_name: str, log: LogSink) -> Digest:
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
