"""The agent's persistent identity.

The control plane pins every REE to the agent id that provisioned it, so an
agent must present the *same* id across restarts or its workbenches become
unreachable. The id is generated once (hostname plus a short random suffix,
so two agents on one box with separate state dirs never collide) and persisted
to a state file that later starts read back.

If the state dir cannot be read or written (say, a read-only filesystem), the
agent still starts — with a warning that its identity is ephemeral and its
REEs will strand on restart — rather than refusing to run.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

_ID_FILENAME = "agent-id"


def generate_agent_id() -> str:
    """A fresh identity: hostname plus a short random suffix.

    The suffix keeps two agents started on one box (each with its own state
    dir) from colliding on a bare hostname."""
    return f"{socket.gethostname()}-{uuid4().hex[:6]}"


def load_or_create_agent_id(state_dir: Path) -> str:
    """Return the persisted agent id, minting and persisting one if absent.

    An empty or whitespace-only id file counts as absent and is rewritten."""
    id_file = state_dir / _ID_FILENAME
    try:
        agent_id = id_file.read_text().strip()
        if agent_id:
            return agent_id
    except FileNotFoundError:
        pass
    except OSError as exc:
        return _ephemeral_fallback(id_file, exc)

    agent_id = generate_agent_id()
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        id_file.write_text(agent_id + "\n")
    except OSError as exc:
        return _ephemeral_fallback(id_file, exc)
    logger.info("minted agent id %s (persisted to %s)", agent_id, id_file)
    return agent_id


def _ephemeral_fallback(id_file: Path, exc: OSError) -> str:
    agent_id = generate_agent_id()
    logger.warning(
        "cannot persist agent id at %s (%s); using ephemeral id %s — "
        "identity will not survive a restart and pinned REEs will strand",
        id_file,
        exc,
        agent_id,
    )
    return agent_id
