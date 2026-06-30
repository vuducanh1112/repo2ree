from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.envelope.handlers import remove_source as handler
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.model import WorkspaceMetadata


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


def test_remove_source_recreates_reserved_build_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReeStore(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    store.ensure_reserved_overlay_scripts()
    store.overlay.write_text(RESERVED_BUILD_SCRIPT, "echo build")
    store.workspace.write_text(RESERVED_BUILD_SCRIPT, "echo build")
    store.upstream.write_text("old.txt", "old source")
    store.artifacts.write_text("runtime.tar.gz", "old runtime")
    store.layout.snapshot_archive.write_text("old snapshot")
    store.layout.acquire_script.write_text("old acquire")
    store.layout.manifest.write_text("{}")
    store.layout.sealed_archive.write_bytes(b"old sealed archive")
    store.write_metadata(
        WorkspaceMetadata(
            reeId="ree123",
            name="demo",
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-01T00:00:00Z",
            reeIntent=ReeIntent(
                name="demo",
                origin_url="https://example.com/old.git",
                source_type="git",
                runtime="runtime.tar.gz",
            ),
            reeSession=ReeSession(source_available=True, sealed_at="2026-01-02T00:00:00Z", seal_hash="sha256:old"),
        )
    )

    monkeypatch.setattr(handler.ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))

    result = handler.handle_remove_source(log=_silent_log, is_canceled=_never_canceled)

    assert result.status == "succeeded"
    assert store.overlay.exists(RESERVED_BUILD_SCRIPT)
    assert store.workspace.exists(RESERVED_BUILD_SCRIPT)
    assert not store.upstream.exists("old.txt")
    assert not store.artifacts.exists("runtime.tar.gz")
    assert not store.layout.snapshot_archive.exists()
    assert not store.layout.acquire_script.exists()
    assert not store.layout.manifest.exists()
    assert not store.layout.sealed_archive.exists()

    metadata = store.read_metadata()
    assert metadata.name == "demo"
    assert metadata.status == "draft"
    assert metadata.external_ref is None
    assert metadata.ree_intent == ReeIntent(name="demo")
    assert metadata.ree_session == ReeSession()
