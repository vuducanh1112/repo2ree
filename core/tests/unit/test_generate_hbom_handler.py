"""Unit coverage for the generate_hbom operations handler.

The handler profiles the workbench hardware and merges it into the persisted
ree intent. These tests point ``ReeLayout.in_workbench`` at a tmp root and stub
``generate_hbom`` so the outcome is deterministic regardless of the host — the
handler's own logic (guards, merge, persistence) is what's under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.domain.hbom import HBOM, CPUDefinition, GPUDefinition
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.operations.handlers.author import generate_hbom as handler
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.model import WorkspaceMetadata


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


def _seed_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, existing: HBOM | None = None) -> ReeStore:
    store = ReeStore(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    store.write_metadata(
        WorkspaceMetadata(
            ree_id="ree123",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(name="demo", hardware_description=existing or HBOM()),
            ree_session=ReeSession(source_available=True),
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return store


def test_missing_metadata_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReeStore(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    result = handler.handle_generate_hbom(log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "failed"
    assert result.exit_code == 1


def test_profiling_failure_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_store(tmp_path, monkeypatch)

    def boom() -> HBOM:
        raise RuntimeError("no /proc here")

    monkeypatch.setattr(handler, "generate_hbom", boom)
    result = handler.handle_generate_hbom(log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "failed"
    assert result.exit_code == 1


def test_profiles_and_persists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _seed_store(tmp_path, monkeypatch)
    profiled = HBOM(cpus={"Xeon": CPUDefinition(quantity=2)})
    monkeypatch.setattr(handler, "generate_hbom", lambda: profiled)

    result = handler.handle_generate_hbom(log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "succeeded"
    assert result.outputs is not None
    assert result.outputs["component_counts"]["cpus"] == 1
    # The profiled hardware landed in the persisted intent.
    persisted = store.read_intent().hardware_description
    assert "Xeon" in persisted.cpus


def test_existing_hardware_wins_on_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Pre-recorded hardware takes precedence over a freshly profiled entry with
    # the same key (existing spread last in the handler's merge).
    existing = HBOM(gpus={"A100": GPUDefinition(vendor="NVIDIA", quantity=8)})
    store = _seed_store(tmp_path, monkeypatch, existing=existing)
    profiled = HBOM(gpus={"A100": GPUDefinition(vendor="NVIDIA", quantity=1)})
    monkeypatch.setattr(handler, "generate_hbom", lambda: profiled)

    result = handler.handle_generate_hbom(log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "succeeded"
    persisted = store.read_intent().hardware_description
    assert persisted.gpus["A100"].quantity == 8
