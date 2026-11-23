from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from repo2ree_core.operations.handlers.author import acquire_source, remove_source
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import AcquireSourceArgs


def _workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ReeLayout, ReeDirectory]:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    initialize_ree(layout, name="local")
    return layout, store


def _commit(origin: Path, content: str) -> str:
    (origin / "hello.txt").write_text(content)
    git = ["git", "-C", str(origin), "-c", "user.name=Test", "-c", "user.email=test@example.test"]
    subprocess.run([*git, "add", "hello.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", content.strip()], check=True)
    return subprocess.run(
        [*git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _local_git_origin(tmp_path: Path) -> tuple[Path, str]:
    if shutil.which("git") is None:
        pytest.skip("git is required for local acquisition integration")
    origin = tmp_path / "origin"
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    return origin, _commit(origin, "first\n")


def test_local_git_download_remove_and_reacquire(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout, store = _workbench(tmp_path, monkeypatch)
    origin, first_revision = _local_git_origin(tmp_path)

    acquired = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url=str(origin),
            source_type="git",
            revision=first_revision,
        ),
        run_id="source-first",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert acquired.status == "succeeded"
    assert layout.snapshot_archive.is_file()
    assert (layout.workspace / "hello.txt").read_text() == "first\n"
    first_receipt = store.read_ree().subject.receipts.acquire_source
    assert first_receipt is not None
    assert first_receipt.resolved_revision == first_revision

    removed = remove_source.handle_remove_source(log=lambda *args: None, is_canceled=lambda: False, layout=layout)
    assert removed.status == "succeeded"
    assert store.read_ree().subject.receipts.acquire_source is None
    assert not layout.snapshot_archive.exists()

    second_revision = _commit(origin, "second\n")
    reacquired = acquire_source.handle_acquire_source(
        AcquireSourceArgs(
            mode="download",
            origin_url=str(origin),
            source_type="git",
            revision=second_revision,
        ),
        run_id="source-second",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert reacquired.status == "succeeded"
    assert (layout.workspace / "hello.txt").read_text() == "second\n"
    second_receipt = store.read_ree().subject.receipts.acquire_source
    assert second_receipt is not None
    assert second_receipt.resolved_revision == second_revision


def test_staged_zip_upload_is_snapshotted_extracted_and_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if shutil.which("tar") is None:
        pytest.skip("tar is required for upload acquisition integration")
    layout, store = _workbench(tmp_path, monkeypatch)
    staged = layout.upload_staging_file("upload-1")
    with zipfile.ZipFile(staged, "w") as archive:
        archive.writestr("uploaded.txt", "uploaded\n")

    result = acquire_source.handle_acquire_source(
        AcquireSourceArgs(mode="upload", upload_token="upload-1", archive_name="source.zip"),  # noqa: S106
        run_id="source-upload",
        log=lambda *args: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "succeeded"
    assert not staged.exists()
    assert layout.snapshot_archive.is_file()
    assert (layout.workspace / "uploaded.txt").read_text() == "uploaded\n"
    receipt = store.read_ree().subject.receipts.acquire_source
    assert receipt is not None
    assert receipt.origin_url is None
    assert receipt.source_type == "zip"
    assert receipt.resolved_revision is None
