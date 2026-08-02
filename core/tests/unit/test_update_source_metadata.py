from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.operations.handlers.author import update_source_metadata as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.sidecar import ReeSidecar
from repo2ree_protocol.command import UpdateSourceMetadataArgs


def _seed_workspace(root: Path) -> ReeDirectory:
    """A ready-to-update workspace rooted at ``root`` with an empty upstream tree."""
    store = ReeDirectory(ReeLayout(root=root))
    store.ensure_dirs()
    store.write_sidecar(
        ReeSidecar(
            ree_id="ree123",
            name="demo",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(),
            ree_state=ReeLifecycleState(),
        )
    )
    return store


@pytest.fixture
def workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeDirectory:
    store = _seed_workspace(tmp_path)
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return store


def _never_canceled() -> bool:
    return False


def _silent_log(*_: object) -> None:
    return None


class TestSwhidStamping:
    def test_download_records_swhid_of_upstream_tree(self, workbench: ReeDirectory) -> None:
        (workbench.layout.upstream / "a.txt").write_bytes(b"hello\n")

        result = handler.handle_update_source_metadata(
            UpdateSourceMetadataArgs(mode="download", origin_url="https://x/y.git", source_type="git"),
            log=_silent_log,
            is_canceled=_never_canceled,
        )

        assert result.status == "succeeded"
        intent = workbench.read_sidecar().ree_intent
        # swh:1:dir of a tree holding a single "hello\n" file — git's tree hash.
        assert intent.swhid.startswith("swh:1:dir:")
        assert len(intent.swhid) == len("swh:1:dir:") + 40
        assert intent.origin_url == "https://x/y.git"

    def test_upload_records_swhid(self, workbench: ReeDirectory) -> None:
        (workbench.layout.upstream / "a.txt").write_bytes(b"hello\n")

        result = handler.handle_update_source_metadata(
            UpdateSourceMetadataArgs(mode="upload", archive_name="src.tar.gz"),
            log=_silent_log,
            is_canceled=_never_canceled,
        )

        assert result.status == "succeeded"
        assert workbench.read_sidecar().ree_intent.swhid.startswith("swh:1:dir:")

    def test_missing_upstream_leaves_swhid_empty_and_still_succeeds(self, workbench: ReeDirectory) -> None:
        # ensure_dirs created an empty upstream dir; remove it to force a failure.
        workbench.layout.upstream.rmdir()

        result = handler.handle_update_source_metadata(
            UpdateSourceMetadataArgs(mode="download", origin_url="https://x/y.git", source_type="git"),
            log=_silent_log,
            is_canceled=_never_canceled,
        )

        assert result.status == "succeeded"
        assert workbench.read_sidecar().ree_intent.swhid == ""


class TestRevisionStamping:
    def test_git_download_records_head_commit_as_revision(self, workbench: ReeDirectory) -> None:
        import subprocess

        upstream = workbench.layout.upstream
        git = ["git", "-C", str(upstream), "-c", "user.name=t", "-c", "user.email=t@e"]
        subprocess.run(["git", "init", "-q", str(upstream)], check=True)
        (upstream / "a.txt").write_bytes(b"hello\n")
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "first"], check=True)
        head = subprocess.run([*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

        result = handler.handle_update_source_metadata(
            UpdateSourceMetadataArgs(mode="download", origin_url="https://x/y.git", source_type="git"),
            log=_silent_log,
            is_canceled=_never_canceled,
        )

        assert result.status == "succeeded"
        meta = workbench.read_sidecar()
        # The resolved commit is settled onto the intent (for seal pinning) and the session.
        assert meta.ree_intent.revision == head
        assert meta.ree_state.source_resolved_commit == head

    def test_non_git_download_leaves_revision_empty(self, workbench: ReeDirectory) -> None:
        result = handler.handle_update_source_metadata(
            UpdateSourceMetadataArgs(mode="download", origin_url="https://x/y.tgz", source_type="tarball"),
            log=_silent_log,
            is_canceled=_never_canceled,
        )

        assert result.status == "succeeded"
        assert workbench.read_sidecar().ree_intent.revision == ""
