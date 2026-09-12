"""History reads and portable downloads preserve prior state and operation records."""

import io
import json
import subprocess
import zipfile

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.tooling import find_tool
from repo2ree_protocol.command import PatchReeDefinitionArgs, PatchReeDefinitionCommand


def _patch(name):
    return run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": name})), log=lambda *args: None
    )


def test_read_history_orders_attempts_and_preserves_legacy_records(tmp_path, monkeypatch):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="first")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    first = _patch("second")
    _patch("second")
    records = read_operation_history(layout).operations
    assert [record.sequence for record in records] == [2, 1]
    assert records[0].before_snapshot_id != records[0].after_snapshot_id
    assert records[0].changed is False
    assert records[1].command["args"]["patch"] == {"name": "second"}
    legacy = records[1].model_dump(mode="json", exclude={"sequence", "context", "result", "changed"})
    legacy["attempt_id"] = "legacy"
    path = layout.git_dir / "repo2ree" / "operations" / "legacy.json"
    path.write_text(json.dumps(legacy))
    assert read_operation_history(layout).operations[-1].sequence is None
    assert first.history.capture_status == "captured"


def test_download_contains_inspectable_git_and_loadable_portable_bundle(tmp_path, monkeypatch):
    from repo2ree_core.operations.handlers.author.load_ree_bundle import handle_load_ree_bundle
    from repo2ree_protocol.command import LoadReeBundleArgs

    layout = ReeLayout(root=tmp_path / "ree")
    initial = initialize_ree(layout, name="before").snapshot_id
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    _patch("after")
    review = layout.review("review-1")
    with open_history(review) as history:
        review.overlay.mkdir(parents=True)
        review.overlay_file("review.txt").write_text("evidence")
        review_head = history.capture(operation="review")
    with materialized_ree_download(layout) as download:
        payload = download.read_bytes()
        with zipfile.ZipFile(download) as archive:
            archive.extractall(tmp_path / "export")
            with zipfile.ZipFile(io.BytesIO(archive.read("ree.zip"))) as portable:
                assert json.loads(portable.read("ree/ree.json"))["subject"]["definition"]["name"] == "after"
    executable = find_tool("git")
    assert executable is not None
    exported = tmp_path / "export" / "ree"
    before = subprocess.check_output([executable, "--git-dir", str(exported / ".git"), "show", f"{initial}:ree.json"])
    assert json.loads(before)["subject"]["definition"]["name"] == "before"
    assert read_operation_history(ReeLayout(root=exported)).operations[0].command["args"]["patch"] == {"name": "after"}
    assert (
        subprocess.check_output(
            [
                executable,
                "--git-dir",
                str(exported / "reviews/review-1/.git"),
                "show",
                f"{review_head}:overlay/review.txt",
            ]
        )
        == b"evidence"
    )

    destination = ReeLayout(root=tmp_path / "destination")
    destination_initial = initialize_ree(destination, name="blank").snapshot_id
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: destination))
    destination.upload_staging_file("download").write_bytes(payload)
    result = handle_load_ree_bundle(
        LoadReeBundleArgs(upload_token="download", archive_name="download.zip"),  # noqa: S106 — local staging identifier
        log=lambda *args: None,
        is_canceled=lambda: False,
    )
    assert result.status == "succeeded"
    assert json.loads(destination.manifest.read_bytes())["subject"]["definition"]["name"] == "after"
    with open_history(destination) as history:
        assert history.initial_snapshot() == destination_initial
    assert read_operation_history(destination).operations == []


def test_export_holds_lock_only_while_staging(tmp_path):
    import fcntl

    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="test")
    with materialized_ree_download(layout) as download:
        assert download.exists()
        with (layout.git_dir / "repo2ree.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert not download.exists()
