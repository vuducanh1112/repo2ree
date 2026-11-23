from __future__ import annotations

import socket
from pathlib import Path

from repo2ree_workbench.identity import load_or_create_workbench_id


def test_mints_and_persists_on_first_call(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"

    workbench_id = load_or_create_workbench_id(state_dir)

    assert workbench_id.startswith(socket.gethostname() + "-")
    assert (state_dir / "workbench-id").read_text().strip() == workbench_id


def test_returns_same_id_across_calls(tmp_path: Path) -> None:
    first = load_or_create_workbench_id(tmp_path)
    second = load_or_create_workbench_id(tmp_path)

    assert first == second


def test_blank_id_file_is_regenerated_and_rewritten(tmp_path: Path) -> None:
    (tmp_path / "workbench-id").write_text("  \n")

    workbench_id = load_or_create_workbench_id(tmp_path)

    assert workbench_id
    assert (tmp_path / "workbench-id").read_text().strip() == workbench_id


def test_unwritable_state_dir_falls_back_to_ephemeral_id(tmp_path: Path) -> None:
    bogus_dir = tmp_path / "not-a-dir"
    bogus_dir.write_text("occupied")

    workbench_id = load_or_create_workbench_id(bogus_dir)

    assert workbench_id.startswith(socket.gethostname() + "-")
