"""The workbench's persistent identity.

The control plane pins every REE to the workbench id that provisioned it, so an
workbench must present the *same* id across restarts or its workbenches become
unreachable. The id is generated once (hostname plus a short random suffix,
so two workbenches on one box with separate state dirs never collide) and persisted
to a state file that later starts read back.

If the state dir cannot be read or written (say, a read-only filesystem), the
workbench still starts — with a warning that its identity is ephemeral and its
REEs will strand on restart — rather than refusing to run.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

_ID_FILENAME = "workbench-id"


def generate_workbench_id() -> str:
    """A fresh identity: hostname plus a short random suffix.

    The suffix keeps two workbenches started on one box (each with its own state
    dir) from colliding on a bare hostname."""
    return f"{socket.gethostname()}-{uuid4().hex[:6]}"


def load_or_create_workbench_id(state_dir: Path) -> str:
    """Return the persisted workbench id, minting and persisting one if absent.

    An empty or whitespace-only id file counts as absent and is rewritten."""
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
