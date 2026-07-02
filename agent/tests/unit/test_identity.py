"""Persisted agent identity (``load_or_create_agent_id``).

The contract under test: the first start mints an id and persists it, every
later start reads the same one back, a blank id file counts as absent, and a
state dir that can't be written degrades to an ephemeral id instead of
refusing to start.
"""

from __future__ import annotations

import socket
from pathlib import Path

from repo2ree_agent.identity import load_or_create_agent_id


def test_mints_and_persists_on_first_call(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"  # does not exist yet; must be created

    agent_id = load_or_create_agent_id(state_dir)

    assert agent_id.startswith(socket.gethostname() + "-")
    assert (state_dir / "agent-id").read_text().strip() == agent_id


def test_returns_same_id_across_calls(tmp_path: Path) -> None:
    first = load_or_create_agent_id(tmp_path)
    second = load_or_create_agent_id(tmp_path)

    assert first == second


def test_blank_id_file_is_regenerated_and_rewritten(tmp_path: Path) -> None:
    (tmp_path / "agent-id").write_text("  \n")

    agent_id = load_or_create_agent_id(tmp_path)

    assert agent_id
    assert (tmp_path / "agent-id").read_text().strip() == agent_id


def test_unwritable_state_dir_falls_back_to_ephemeral_id(tmp_path: Path) -> None:
    # A *file* where the state dir should be makes both read and mkdir fail —
    # an OSError either way, like a read-only filesystem would raise.
    bogus_dir = tmp_path / "not-a-dir"
    bogus_dir.write_text("occupied")

    agent_id = load_or_create_agent_id(bogus_dir)

    assert agent_id.startswith(socket.gethostname() + "-")
