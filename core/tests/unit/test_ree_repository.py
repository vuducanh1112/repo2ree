"""Assembly of the canonical REE from the existing persisted stores."""

from pathlib import Path

from repo2ree_core.digests import Digest
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.queries import name_of, scripts_of
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.metadata import WorkspaceMetadata
from repo2ree_core.persistence.repository import load_ree
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import parse_utc_instant


def test_repository_hydrates_authored_evidence_and_publication(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path)
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_text(RESERVED_BUILD_SCRIPT, "build runtime")
    store.write_metadata(
        WorkspaceMetadata(
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
    assert ree.publications.sealed is not None
    assert ree.publications.sealed.seal_hash == "sha256:seal"
