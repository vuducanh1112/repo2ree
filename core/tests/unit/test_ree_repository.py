"""Assembly of the canonical REE from the existing persisted stores."""

from pathlib import Path

import pytest

from repo2ree_core.digests import Digest
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.queries import name_of, scripts_of
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.domain.ree.transitions import SourceSlot, revision_of
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.repository import (
    ReeRevisionConflictError,
    load_ree,
    observe_source_slot,
    save_ree,
)
from repo2ree_core.persistence.sidecar import ReeSidecar
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import parse_utc_instant


def _silent_log(stream: str, level: str, message: str) -> None:
    return None


def test_repository_hydrates_authored_evidence_and_seal(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path)
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_text(RESERVED_BUILD_SCRIPT, "build runtime")
    store.write_sidecar(
        ReeSidecar(
            ree_id="ree-1",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-02T00:00:00Z",
            ree_intent=ReeIntent(name="demo", runtime="runtime.tar"),
            ree_state=ReeLifecycleState(
                source_available=True,
                source_snapshot_digest=Digest("sha256:snapshot"),
                sealed_at=parse_utc_instant("2026-01-02T00:00:00Z"),
                seal_hash=Digest("sha256:seal"),
                source_included=True,
            ),
        )
    )

    ree = load_ree(layout, store)

    assert ree.identity.ree_id == "ree-1"
    assert name_of(ree.authored) == "demo"
    assert scripts_of(ree.authored).build_runtime is not None
    assert ree.evidence.state.source_snapshot_digest == "sha256:snapshot"
    assert ree.seal is not None
    assert ree.seal.seal_hash == "sha256:seal"


# ================================================
# Saving the head back
# ================================================


def _seeded(tmp_path: Path) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(root=tmp_path)
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_sidecar(
        ReeSidecar(
            ree_id="ree-1",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(name="demo"),
        )
    )
    return layout, store


def test_save_ree_commits_intent_and_state_together(tmp_path: Path) -> None:
    layout, store = _seeded(tmp_path)
    ree = load_ree(layout, store)

    updated = ree.model_copy(
        update={
            "authored": ree.authored.model_copy(
                update={"intent": ree.authored.intent.model_copy(update={"origin_url": "https://x/y.git"})}
            ),
            "evidence": ree.evidence.model_copy(
                update={"state": ree.evidence.state.model_copy(update={"source_available": True})}
            ),
        }
    )
    save_ree(layout, store, updated, expected_revision=revision_of(ree), status="ready", log=_silent_log)

    sidecar = store.read_sidecar()
    assert sidecar.status == "ready"
    assert sidecar.ree_intent.origin_url == "https://x/y.git"
    assert sidecar.ree_state.source_available is True
    # name and external_ref stay projections of the intent, re-derived on the way in
    assert sidecar.external_ref == "https://x/y.git"


def test_save_ree_refuses_when_the_head_moved(tmp_path: Path) -> None:
    """A stale save is raised, never merged: reconciling would pick a winner."""
    layout, store = _seeded(tmp_path)
    ree = load_ree(layout, store)
    stale_revision = revision_of(ree)

    # Somebody else writes the head between the hydrate and the save.
    store.write_intent(ree.authored.intent.model_copy(update={"origin_url": "https://other/z.git"}))

    with pytest.raises(ReeRevisionConflictError):
        save_ree(layout, store, ree, expected_revision=stale_revision, log=_silent_log)
    assert store.read_sidecar().ree_intent.origin_url == "https://other/z.git"


def test_revision_covers_the_whole_head(tmp_path: Path) -> None:
    """Intent, authored files, and state are one transactional scope."""
    layout, store = _seeded(tmp_path)
    base = revision_of(load_ree(layout, store))

    store.overlay.write_text("notes.md", "hello")
    with_file = revision_of(load_ree(layout, store))
    assert with_file != base

    store.write_state(ReeLifecycleState(dependency_level=3))
    with_state = revision_of(load_ree(layout, store))
    assert with_state != with_file


def test_observe_source_slot_sees_what_the_state_does_not(tmp_path: Path) -> None:
    """An acquisition killed mid-effect shows up here and nowhere else."""
    layout, store = _seeded(tmp_path)
    assert observe_source_slot(layout) == SourceSlot(
        upstream_populated=False,
        snapshot_archive_present=False,
        staged_upload_present=False,
    )

    (layout.upstream / "half-fetched.py").write_text("partial")
    slot = observe_source_slot(layout)
    assert slot.upstream_populated is True
    assert store.read_state().source_available is False


def test_observe_source_slot_narrows_staging_to_one_token(tmp_path: Path) -> None:
    layout, _ = _seeded(tmp_path)
    staged, other = "tok-a", "tok-b"  # upload-staging ids, not secrets
    layout.upload_staging_file(staged).write_bytes(b"bytes")

    assert observe_source_slot(layout, upload_token=staged).staged_upload_present is True
    assert observe_source_slot(layout, upload_token=other).staged_upload_present is False
    assert observe_source_slot(layout).staged_upload_present is False
