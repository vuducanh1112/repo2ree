"""Persistent identity for a Docker provider instance."""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


def load_or_create_provider_id(state_dir: Path) -> str:
    id_file = state_dir / "provider-id"
    try:
        provider_id = id_file.read_text().strip()
        if provider_id:
            return provider_id
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("cannot read provider identity at %s: %s", id_file, exc)
    provider_id = f"docker-{socket.gethostname()}-{uuid4().hex[:6]}"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        id_file.write_text(provider_id + "\n")
    except OSError as exc:
        logger.warning("cannot persist provider identity at %s: %s", id_file, exc)
    return provider_id
