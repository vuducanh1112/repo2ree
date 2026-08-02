"""Atomic optimistic concurrency for intent mutations."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.operations.handlers.author import patch_ree_intent as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.sidecar import ReeSidecar
from repo2ree_protocol.command import PatchReeIntentArgs

_VERSION = "2026-01-02T00:00:00Z"


def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeDirectory:
    store = ReeDirectory(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    store.write_sidecar(
        ReeSidecar(
            ree_id="ree-1",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at=_VERSION,
            ree_intent=ReeIntent(name="demo"),
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return store


def test_stale_expected_version_conflicts_without_mutating(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)

    result = handler.handle_patch_ree_intent(
        PatchReeIntentArgs(patch={"name": "changed"}, expected_version="stale"),
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "conflict"
    # The same shape a file etag conflict reports, minus the path an intent
    # conflict has no equivalent of.
    assert result.outputs == {
        "error_code": "version_conflict",
        "expected_version": "stale",
        "actual_version": _VERSION,
    }
    assert store.read_intent().name == "demo"


def test_matching_expected_version_mutates_intent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _store(tmp_path, monkeypatch)

    result = handler.handle_patch_ree_intent(
        PatchReeIntentArgs(patch={"name": "changed"}, expected_version=_VERSION),
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert store.read_intent().name == "changed"
