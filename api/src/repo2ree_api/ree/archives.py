"""Archive response naming and spool streaming helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import IO

from repo2ree_api.deps import workbench_manager
from repo2ree_supervisor import WorkbenchHandle


def archive_download_filename(handle: WorkbenchHandle) -> str:
    metadata = workbench_manager.get_ree_metadata(handle)
    raw_name = str(metadata.get("name") or "").strip()
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._-")
    return f"{safe_stem or 'ree'}.zip"


def spool_chunks(spool: IO[bytes]) -> Iterator[bytes]:
    try:
        while chunk := spool.read(64 * 1024):
            yield chunk
    finally:
        spool.close()
