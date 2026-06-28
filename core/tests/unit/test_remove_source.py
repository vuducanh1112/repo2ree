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
    store.write_metadata(
        WorkspaceMetadata(
            reeId="ree123",
            name="demo",
            createdAt="2026-01-01T00:00:00Z",
            updatedAt="2026-01-01T00:00:00Z",
            reeIntent=ReeIntent(name="demo"),
            reeSession=ReeSession(source_available=True),
        )
    )

    monkeypatch.setattr(handler.ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))

    result = handler.handle_remove_source(log=_silent_log, is_canceled=_never_canceled)

    assert result.status == "succeeded"
    assert store.overlay.exists(RESERVED_BUILD_SCRIPT)
    assert store.workspace.exists(RESERVED_BUILD_SCRIPT)
