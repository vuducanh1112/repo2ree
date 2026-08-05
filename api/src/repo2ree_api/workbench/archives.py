"""Archive response naming and spool streaming helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import IO

from repo2ree_api.deps import workbench_manager
from repo2ree_core.domain.ree.model import Ree
from repo2ree_supervisor import WorkbenchHandle


def archive_download_filename(handle: WorkbenchHandle) -> str:
    """Name the downloaded bundle after the REE it holds.

    Parsed rather than indexed. This read was ``metadata.get("name")`` against
    the raw document, which has no top-level ``name`` — the REE's name lives at
    ``subject.definition.name``. ``.get`` answered ``None`` instead of raising,
    so every bundle downloaded as ``ree.zip`` and the fallback below hid it.
    Three refactors renamed the *source* of this dict without anyone noticing
    the *path* into it had stopped meaning anything.
    """
    ree = Ree.model_validate(workbench_manager.get_ree_manifest(handle))
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ree.subject.definition.name.strip()).strip("._-")
    return f"{safe_stem or 'ree'}.zip"


def spool_chunks(spool: IO[bytes]) -> Iterator[bytes]:
    try:
        while chunk := spool.read(64 * 1024):
            yield chunk
    finally:
        spool.close()
