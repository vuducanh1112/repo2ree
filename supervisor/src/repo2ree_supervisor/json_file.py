"""A JSON document replaced whole, so a reader or a crash never sees half of one.

A crash of the process, that is: as core's ``write_atomic``, nothing is synced, so a power loss
may lose the last write. These files outlive an API restart, which is what they are for.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path: Path, data: object) -> None:
    """Write ``data`` beside ``path`` and rename it over; the file is readable by its owner only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True)
        Path(temporary).replace(path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
