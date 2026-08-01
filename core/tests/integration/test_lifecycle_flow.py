"""End-to-end flow test for the REE lifecycle.

This is a *flow* test, not a unit test: it drives the real ``run_command`` dispatcher
dispatcher through the sequence of typed commands that make up the REE
lifecycle described in docs/REE.md, asserting the state of the durable
``/ree`` tree after each transition.

    acquire_source -> snapshot_upstream -> materialize_workspace
        -> write_file -> (re-materialize) -> seal_ree

It exercises every layer the control plane sits on top of — the command
the command envelope, the dispatcher, the handlers, and the ``ReeDirectory`` / ``ReeLayout``
filesystem shell — with no Docker, no HTTP, and no container transport.

Nothing here is mocked. ``git`` runs for real against a local fixture
repository (no network); the snapshot/materialize/overlay/seal steps are
real filesystem operations. The only test-only seam is redirecting the
``WORKBENCH_ROOT`` constant to a temp dir — the same real handler code,
rooted at ``tmp_path`` instead of ``/ree``, not a behavior stub.

Steps that require a real external tool are tested for real where that tool
exists, and skipped (never faked) when it is absent:
  * ``build_runtime`` / ``run_experiment`` / ``activation_test`` /
    ``generate_sbom`` need a Docker daemon — their home is the Docker-gated e2e.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import pytest

import repo2ree_core.persistence.layout as layout_mod
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.state import ReeLifecycleState, is_sealed
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.time_utils import utc_now
from repo2ree_protocol.command import (
    AcquireSourceArgs,
    AcquireSourceCommand,
    EvaluateDependencyScoreCommand,
    ExtractUploadArgs,
    ExtractUploadCommand,
    MaterializeWorkspaceCommand,
    ResetForSourceChangeCommand,
    SealReeCommand,
    SnapshotUpstreamCommand,
    UpdateSourceMetadataArgs,
    UpdateSourceMetadataCommand,
    WriteFileArgs,
    WriteFileCommand,
)

# ================================================
# Test infrastructure
# ================================================


@dataclass
class LogCollector:
    """A LogSink that records the NDJSON log events handlers emit.

    The supervisor streams these back to the API over stderr; here we just
    keep them so the test can assert the flow produced log output.
    """

    events: list[tuple[str, str, str]] = field(default_factory=list)

    def __call__(self, stream: str, level: str, message: str) -> None:
        self.events.append((stream, level, message))


@dataclass
class Ree:
    """Handle to a temp REE wired up to look like the workbench's /ree tree."""

    layout: ReeLayout
    ree_id: str
    log: LogCollector

    def session(self) -> ReeLifecycleState:
        return ReeDirectory(self.layout).read_state()


def _make_source_repo(
    root: Path,
    *,
    name: str = "source-repo",
    app_text: str = "print('hello')\n",
    extra_files: dict[str, str] | None = None,
) -> Path:
    """Create a small local git repo to stand in for an upstream source."""
    repo = root / name
    repo.mkdir()
    (repo / "README.md").write_text("# demo project\n")
    (repo / "requirements.txt").write_text("requests==2.31.0\n")
    (repo / "Dockerfile").write_text("FROM python:3.13-slim\n")
    (repo / "app.py").write_text(app_text)
    for rel, content in (extra_files or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def _git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    _git("init", "-q")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test")
    _git("add", ".")
    _git("commit", "-q", "-m", "initial commit")
    return repo


def _init_ree(layout: ReeLayout, ree_id: str) -> None:
    """Bootstrap the REE tree + initial metadata, mirroring ``init-ree``."""
    store = ReeDirectory(layout)
    store.ensure_dirs()
    ts = utc_now()
    name = f"workspace-{ree_id[:8]}"
    store.write_metadata_json(
        {
            "ree_id": ree_id,
            "external_ref": None,
            "name": name,
            "status": "draft",
            "created_at": ts,
            "updated_at": ts,
            "ree_intent": ReeIntent(name=name).model_dump(exclude_none=True),
            "ree_state": ReeLifecycleState().model_dump(exclude_none=True),
        }
    )


# ================================================
# Fixtures
# ================================================


@pytest.fixture
def source_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_source_repo(tmp_path_factory.mktemp("upstream"))


@pytest.fixture
def ree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Ree:
    """A temp REE whose root masquerades as the workbench mount point.

    Handlers resolve their root via ``ReeLayout.in_workbench()``, which reads
    the module-level ``WORKBENCH_ROOT`` at call time — so redirecting that
    constant points the whole core at this temp tree.
    """
    ree_id = uuid4().hex
    ree_root = tmp_path / ree_id
    monkeypatch.setattr(layout_mod, "WORKBENCH_ROOT", ree_root)

    layout = ReeLayout.in_workbench()
    assert layout.root == ree_root
    _init_ree(layout, ree_id)
    return Ree(layout=layout, ree_id=ree_id, log=LogCollector())


# ================================================
# Flow test
# ================================================


def test_ree_lifecycle_flow(ree: Ree, source_repo: Path) -> None:
    layout = ree.layout
    log = ree.log

    # --- acquire_source: clone upstream into upstream/ ------------------
    result = run_command(
        AcquireSourceCommand(args=AcquireSourceArgs(origin_url=str(source_repo), source_type="git")),
        log=log,
        run_id="acquire",
    )
    assert result.status == "succeeded"
    assert (layout.upstream / "requirements.txt").is_file()
    assert (layout.upstream / "app.py").is_file()
    # the fetch was driven by a persisted, REE-owned acquire script (the same
    # file run.sh will eventually call), not a throwaway temp
    assert layout.acquire_script.is_file()
    assert "git clone" in layout.acquire_script.read_text()
    assert str(source_repo) in layout.acquire_script.read_text()

    # --- snapshot_upstream: freeze upstream into snapshot.tar.gz --------
    result = run_command(SnapshotUpstreamCommand(), log=log, run_id="snapshot")
    assert result.status == "succeeded"
    assert layout.snapshot_archive.is_file()

    # --- materialize_workspace: upstream -> workspace ------------------
    result = run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize")
    assert result.status == "succeeded"
    assert (layout.workspace / "requirements.txt").is_file()
    assert (layout.workspace / "app.py").is_file()

    # --- write_file: the overlay's contribution beside the source ------
    result = run_command(
        WriteFileCommand(args=WriteFileArgs(path="build.sh", content="echo build\n")),
        log=log,
        run_id="write",
    )
    assert result.status == "succeeded"
    assert (layout.overlay / "build.sh").is_file()
    assert (layout.workspace / "build.sh").is_file()

    # --- re-materialize: overlay survives a rebuild, upstream intact ---
    result = run_command(MaterializeWorkspaceCommand(), log=log, run_id="rematerialize")
    assert result.status == "succeeded"
    assert (layout.workspace / "build.sh").read_text() == "echo build\n"
    assert (layout.workspace / "requirements.txt").is_file()

    # --- seal_ree: produce the immutable sealed bundle -----------------
    result = run_command(SealReeCommand(), log=log, run_id="seal")
    assert result.status == "succeeded"
    assert layout.sealed_archive.is_file()
    assert layout.manifest.is_file()
    assert result.outputs["seal_hash"].startswith("sha256:")

    sealed_session = ree.session()
    assert is_sealed(sealed_session)
    assert sealed_session.seal_hash == result.outputs["seal_hash"]

    # the flow streamed log events at every step (the supervisor's relay path)
    assert log.events


def test_upload_pipeline_extract_then_acquire(ree: Ree, tmp_path: Path) -> None:
    """Upload path: extract_upload builds the snapshot, then acquire extracts it.

    Mirrors the API's _upload_pipeline (extract_upload -> acquire -> materialize),
    proving an origin-less source is populated through the same unified acquire.
    """
    layout = ree.layout
    log = ree.log

    # Stage an uploaded tarball at /ree/upload-staging/<token>.bin
    src = tmp_path / "proj"
    src.mkdir()
    (src / "main.py").write_text("print('uploaded')\n")
    (src / "data.txt").write_text("payload\n")
    token = "tok123"  # noqa: S105 — not a secret, just an upload-staging id
    layout.upload_staging.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-czf", str(layout.upload_staging_file(token)), "-C", str(src), "."],
        check=True,
    )

    # extract_upload turns the staged bytes into the snapshot (not upstream)
    result = run_command(
        ExtractUploadCommand(args=ExtractUploadArgs(upload_token=token, archive_name="proj.tar.gz")),
        log=log,
        run_id="extract-upload",
    )
    assert result.status == "succeeded"
    assert layout.snapshot_archive.is_file()
    assert not layout.upstream.exists() or not any(layout.upstream.iterdir())

    # acquire (no origin/type) extracts the snapshot into upstream
    result = run_command(
        AcquireSourceCommand(args=AcquireSourceArgs()),
        log=log,
        run_id="acquire-upload",
    )
    assert result.status == "succeeded"
    assert (layout.upstream / "main.py").read_text() == "print('uploaded')\n"
    assert (layout.upstream / "data.txt").is_file()

    # and it flows on into the workspace
    result = run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize-upload")
    assert result.status == "succeeded"
    assert (layout.workspace / "main.py").is_file()


def test_source_replacement_resets_derived_state_before_download(ree: Ree, source_repo: Path, tmp_path: Path) -> None:
    layout = ree.layout
    log = ree.log
    replacement_repo = _make_source_repo(
        tmp_path,
        name="replacement-repo",
        app_text="print('replacement')\n",
        extra_files={"replacement-only.txt": "new\n"},
    )

    # Seed a complete old source/runtime/seal state.
    run_command(
        AcquireSourceCommand(args=AcquireSourceArgs(origin_url=str(source_repo), source_type="git")),
        log=log,
        run_id="acquire-old",
    )
    run_command(SnapshotUpstreamCommand(), log=log, run_id="snapshot-old")
    run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize-old")
    run_command(
        WriteFileCommand(args=WriteFileArgs(path="old-overlay.sh", content="echo stale\n")),
        log=log,
        run_id="write-old",
    )
    (layout.artifacts / "runtime.tar.gz").write_text("old runtime\n")
    run_command(SealReeCommand(), log=log, run_id="seal-old")
    assert layout.snapshot_archive.is_file()
    assert layout.sealed_archive.is_file()

    # Simulate the API download pipeline for a replacement source.
    result = run_command(ResetForSourceChangeCommand(), log=log, run_id="reset-source")
    assert result.status == "succeeded"
    result = run_command(
        AcquireSourceCommand(args=AcquireSourceArgs(origin_url=str(replacement_repo), source_type="git")),
        log=log,
        run_id="acquire-new",
    )
    assert result.status == "succeeded"
    run_command(SnapshotUpstreamCommand(), log=log, run_id="snapshot-new")
    run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize-new")
    run_command(
        UpdateSourceMetadataCommand(
            args=UpdateSourceMetadataArgs(
                origin_url=str(replacement_repo),
                source_type="git",
            )
        ),
        log=log,
        run_id="metadata-new",
    )

    assert (layout.upstream / "app.py").read_text() == "print('replacement')\n"
    assert (layout.workspace / "replacement-only.txt").read_text() == "new\n"
    assert not (layout.workspace / "old-overlay.sh").exists()
    assert not (layout.artifacts / "runtime.tar.gz").exists()
    assert not layout.sealed_archive.exists()
    assert not layout.manifest.exists()
    assert str(replacement_repo) in layout.acquire_script.read_text()

    metadata = ReeDirectory(layout).read_metadata()
    assert metadata.status == "ready"
    assert metadata.ree_intent.origin_url == str(replacement_repo)
    assert metadata.ree_state.source_acquired_by == "download"


def test_source_replacement_resets_derived_state_before_upload(ree: Ree, source_repo: Path, tmp_path: Path) -> None:
    layout = ree.layout
    log = ree.log

    run_command(
        AcquireSourceCommand(args=AcquireSourceArgs(origin_url=str(source_repo), source_type="git")),
        log=log,
        run_id="acquire-old-upload",
    )
    run_command(SnapshotUpstreamCommand(), log=log, run_id="snapshot-old-upload")
    run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize-old-upload")
    (layout.workspace / "stale-workspace.txt").write_text("stale\n")

    src = tmp_path / "uploaded-replacement"
    src.mkdir()
    (src / "main.py").write_text("print('uploaded replacement')\n")
    token = "tok456"  # noqa: S105 — not a secret, just an upload-staging id
    layout.upload_staging.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "-czf", str(layout.upload_staging_file(token)), "-C", str(src), "."],
        check=True,
    )

    # Simulate the API upload pipeline for a replacement source. Reset must not
    # remove upload staging, because extract_upload consumes it next.
    result = run_command(ResetForSourceChangeCommand(), log=log, run_id="reset-upload")
    assert result.status == "succeeded"
    assert layout.upload_staging_file(token).is_file()
    result = run_command(
        ExtractUploadCommand(args=ExtractUploadArgs(upload_token=token, archive_name="replacement.tar.gz")),
        log=log,
        run_id="extract-upload-replacement",
    )
    assert result.status == "succeeded"
    result = run_command(AcquireSourceCommand(args=AcquireSourceArgs()), log=log, run_id="acquire-upload-new")
    assert result.status == "succeeded"
    run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize-upload-new")
    run_command(
        UpdateSourceMetadataCommand(args=UpdateSourceMetadataArgs(mode="upload", archive_name="replacement.tar.gz")),
        log=log,
        run_id="metadata-upload-new",
    )

    assert (layout.upstream / "main.py").read_text() == "print('uploaded replacement')\n"
    assert (layout.workspace / "main.py").is_file()
    assert not (layout.workspace / "stale-workspace.txt").exists()
    assert not (layout.workspace / "requirements.txt").exists()

    metadata = ReeDirectory(layout).read_metadata()
    assert metadata.status == "ready"
    assert metadata.ree_intent.origin_url == ""
    assert metadata.ree_state.source_acquired_by == "upload"


def test_seal_is_deterministic_for_unchanged_content(ree: Ree, source_repo: Path) -> None:
    """Re-sealing unchanged content reproduces the same digest.

    This is the content-addressing property the receipt/verify story rests on:
    the seal hash names the bundle's content, not the moment it was sealed.
    """
    log = ree.log

    run_command(
        AcquireSourceCommand(args=AcquireSourceArgs(origin_url=str(source_repo), source_type="git")),
        log=log,
        run_id="acquire",
    )
    run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize")

    first = run_command(SealReeCommand(), log=log, run_id="seal-1")
    second = run_command(SealReeCommand(), log=log, run_id="seal-2")

    assert first.status == second.status == "succeeded"
    assert first.outputs["seal_hash"] == second.outputs["seal_hash"]


# ================================================
# Tool-gated flow steps
# ================================================


def test_evaluate_dependency_score_real(ree: Ree, source_repo: Path) -> None:
    """Run the scoring on a materialized workspace.

    The manifest scan extracts the fixture's real dependency data: a pinned
    ``requests==2.31.0`` in requirements.txt (no lockfile → Pinned, level 2)
    and a tag-only base image in the Dockerfile.
    """
    layout = ree.layout
    log = ree.log

    run_command(
        AcquireSourceCommand(args=AcquireSourceArgs(origin_url=str(source_repo), source_type="git")),
        log=log,
        run_id="acquire",
    )
    run_command(MaterializeWorkspaceCommand(), log=log, run_id="materialize")

    result = run_command(EvaluateDependencyScoreCommand(), log=log, run_id="evaluate")

    assert result.status == "succeeded"
    assert (layout.artifacts / "reproducibility-report.json").is_file()
    assert result.outputs["manifest_count"] == 1  # requirements.txt (the Dockerfile is the env axis)
    assert result.outputs["dependency_count"] == 1  # requests==2.31.0
    assert result.outputs["dependency_level"] == 2  # pinned, but no lockfile
    # The floating base image is reported as a threat, not counted as a dependency.
    threat_ids = {threat["id"] for threat in result.outputs["report"]["threats"]}
    assert "floating-base-image" in threat_ids
