from __future__ import annotations

import logging
import socket
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

_ID_FILENAME = "workbench-id"


def generate_workbench_id() -> str:
    return f"{socket.gethostname()}-{uuid4().hex[:6]}"


def load_or_create_workbench_id(state_dir: Path) -> str:
    id_file = state_dir / _ID_FILENAME
    try:
        workbench_id = id_file.read_text().strip()
        if workbench_id:
            return workbench_id
    except FileNotFoundError:
        pass
    except OSError as exc:
        return _ephemeral_fallback(id_file, exc)

    workbench_id = generate_workbench_id()
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        id_file.write_text(workbench_id + "\n")
    except OSError as exc:
        return _ephemeral_fallback(id_file, exc)
    logger.info("minted workbench id %s (persisted to %s)", workbench_id, id_file)
    return workbench_id


def _ephemeral_fallback(id_file: Path, exc: OSError) -> str:
    workbench_id = generate_workbench_id()
    logger.warning(
        "cannot persist workbench id at %s (%s); using ephemeral id %s — "
        "identity will not survive a restart and pinned REEs will strand",
        id_file,
        exc,
        workbench_id,
    )
    return workbench_id
