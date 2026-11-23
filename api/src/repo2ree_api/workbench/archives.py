from __future__ import annotations

import re
from collections.abc import Iterator
from typing import IO

from repo2ree_api.deps import command_dispatcher
from repo2ree_supervisor import ReeRoute


def archive_download_filename(handle: ReeRoute) -> str:
    ree = command_dispatcher.get_ree_manifest(handle)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ree.subject.definition.name.strip()).strip("._-")
    return f"{safe_stem or 'ree'}.zip"


def spool_chunks(spool: IO[bytes]) -> Iterator[bytes]:
    try:
        while chunk := spool.read(64 * 1024):
            yield chunk
    finally:
        spool.close()
