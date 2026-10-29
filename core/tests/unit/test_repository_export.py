"""A repository release carries its selected LFS payloads without a server."""

import json
import subprocess
import zipfile

import pytest

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.bundle.repository_restore import restore_repository
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.lfs import LfsPointer
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_core.tooling import find_tool
from repo2ree_protocol.command import LoadReeBundleArgs, LoadReeBundleCommand, SealReeArgs, SealReeCommand
from repo2ree_ree.model import CapturePolicy


def _sealed(tmp_path, monkeypatch):
    layout = ReeLayout(root=tmp_path / "author")
    initialize_ree(layout, name="offline")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    # Result files exercise optional bulk payloads without requiring Docker.
    (layout.results / "experiment").mkdir(parents=True)
    payload = b"binary\0result" * 4096
    (layout.results / "experiment/data.bin").write_bytes(payload)
    result = run_command(
        SealReeCommand(
            args=SealReeArgs(
                source_included=False,
                runtime_included=False,
                results_included=True,
            )
        ),
        log=lambda *args: None,
    )
    assert result.status == "succeeded", result
    assert result.history is not None
    with open_history(layout) as history:
        blob = history.git("show", f"{result.history.after_snapshot_id}:results/experiment/data.bin").stdout
    pointer = LfsPointer.parse(blob)
    assert pointer is not None
    assert pointer.size == len(payload)
    return layout, pointer, payload


def test_seal_export_offline_checkout_and_load_preserve_history(tmp_path, monkeypatch):
    layout, pointer, payload = _sealed(tmp_path, monkeypatch)
    with materialized_ree_download(layout) as archive:
        data = archive.read_bytes()
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(tmp_path / "export")
    exported = tmp_path / "export/ree"
    assert (exported / "results/experiment/data.bin").read_bytes() == payload
    pointer.verify(exported / ".git")
    executable = find_tool("git-lfs")
    assert executable is not None
    (exported / "results/experiment/data.bin").unlink()
    subprocess.run([executable, "checkout"], cwd=exported, check=True, capture_output=True)
    assert (exported / "results/experiment/data.bin").read_bytes() == payload
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="blank")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: destination))
    destination.upload_staging_file("offline").write_bytes(data)
    loaded = run_command(
        LoadReeBundleCommand(
            args=LoadReeBundleArgs(
                upload_token="offline",  # noqa: S106 — staging identity
                archive_name="ree.zip",
            )
        ),
        log=lambda *args: None,
    )
    assert loaded.status == "succeeded", loaded
    records = read_operation_history(destination).operations
    assert {record.command["operation"] for record in records} == {"seal_ree", "load_ree_bundle"}
    assert (destination.results / "experiment/data.bin").read_bytes() == payload
    with materialized_ree_download(destination) as archive, zipfile.ZipFile(archive) as zipped:
        assert zipped.read("ree/results/experiment/data.bin") == payload
        zipped.extractall(tmp_path / "reexport")
    exported_records = read_operation_history(ReeLayout(root=tmp_path / "reexport/ree")).operations
    assert any(record.command["operation"] == "load_ree_bundle" for record in exported_records)


def test_export_rejects_missing_selected_object(tmp_path, monkeypatch):
    layout, pointer, _payload = _sealed(tmp_path, monkeypatch)
    pointer.object_path(layout.git_dir).unlink()
    with pytest.raises(ValueError, match="Missing LFS"), materialized_ree_download(layout):
        pass


def test_new_selection_omits_old_object_without_rewriting_history(tmp_path, monkeypatch):
    layout, pointer, _payload = _sealed(tmp_path, monkeypatch)
    store = ReeDirectory(layout)
    ree = store.read_ree()
    # Test the storage transition without adding a public reopen command.
    store.write_ree(
        ree.model_copy(update={"seal": None, "subject": ree.subject.model_copy(update={"capture": CapturePolicy()})})
    )
    with open_history(layout) as history:
        history.capture(operation="test_selection_change")
    with materialized_ree_download(layout) as archive, zipfile.ZipFile(archive) as zipped:
        assert "ree/results/experiment/data.bin" not in zipped.namelist()
        assert not any(pointer.oid in name for name in zipped.namelist())
        zipped.extractall(tmp_path / "export")
    assert any(
        record.command["operation"] == "seal_ree"
        for record in read_operation_history(ReeLayout(root=tmp_path / "export/ree")).operations
    )


def test_invalid_export_does_not_modify_destination(tmp_path, monkeypatch):
    layout, pointer, _payload = _sealed(tmp_path, monkeypatch)
    with materialized_ree_download(layout) as archive, zipfile.ZipFile(archive) as zipped:
        zipped.extractall(tmp_path / "export")
    pointer.object_path(tmp_path / "export/ree/.git").write_bytes(b"corrupt")
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="untouched")
    with pytest.raises(ValueError, match="Corrupt LFS"):
        restore_repository(destination, tmp_path / "export")
    assert json.loads(destination.manifest.read_text())["subject"]["definition"]["name"] == "untouched"


def test_legacy_sealed_archive_keeps_original_identity_and_bytes(tmp_path):
    from repo2ree_core.bundle.restore import restore_ree_bundle
    from repo2ree_core.domain.ree.transitions import record_seal
    from repo2ree_core.persistence.ree_manifest import ree_manifest_bytes
    from repo2ree_core.time_utils import utc_now_instant
    from repo2ree_ree.model import Ree, ReeSubject

    legacy = record_seal(Ree(subject=ReeSubject()), sealed_at=utc_now_instant())
    extracted = tmp_path / "legacy"
    (extracted / "ree").mkdir(parents=True)
    (extracted / "ree/ree.json").write_bytes(ree_manifest_bytes(legacy))
    archive = tmp_path / "legacy.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.write(extracted / "ree/ree.json", "ree/ree.json")
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="blank")
    restore_ree_bundle(destination, bundle_root=extracted, archive_path=archive)
    assert ReeDirectory(destination).read_ree().seal == legacy.seal
    with materialized_ree_download(destination) as download:
        assert download.read_bytes() == archive.read_bytes()


def test_import_ignores_uploaded_git_configuration(tmp_path, monkeypatch):
    layout, _pointer, _payload = _sealed(tmp_path, monkeypatch)
    with materialized_ree_download(layout) as archive, zipfile.ZipFile(archive) as zipped:
        zipped.extractall(tmp_path / "export")
    git_dir = tmp_path / "export/ree/.git"
    (git_dir / "config").write_text("[include]\npath = /does-not-exist\n[core]\nrepositoryformatversion = 999\n")
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="blank")
    restore_repository(destination, tmp_path / "export")
    assert "999" not in (destination.git_dir / "config").read_text()


@pytest.mark.parametrize("source_included", [False, True])
@pytest.mark.parametrize("runtime_included", [False, True])
@pytest.mark.parametrize("results_included", [False, True])
def test_seal_toggles_are_the_only_optional_payload_selection(
    tmp_path,
    monkeypatch,
    source_included,
    runtime_included,
    results_included,
):
    layout = ReeLayout(root=tmp_path / "author")
    initialize_ree(layout, name="selection")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    store = ReeDirectory(layout)
    ree = store.read_ree()
    definition = ree.subject.definition
    assert definition.build_runtime is not None
    runtime = definition.build_runtime.model_copy(update={"runtime_path": "runtime.tar"})
    store.write_ree(
        ree.model_copy(
            update={
                "subject": ree.subject.model_copy(
                    update={"definition": definition.model_copy(update={"build_runtime": runtime})}
                )
            }
        )
    )
    layout.snapshot_archive.write_bytes(b"source")
    (layout.workspace / "runtime.tar").write_bytes(b"runtime")
    layout.results.mkdir(exist_ok=True)
    (layout.results / "data").write_bytes(b"result")
    result = run_command(
        SealReeCommand(
            args=SealReeArgs(
                source_included=source_included,
                runtime_included=runtime_included,
                results_included=results_included,
            )
        ),
        log=lambda *args: None,
    )
    assert result.status == "succeeded", result
    with materialized_ree_download(layout) as archive, zipfile.ZipFile(archive) as zipped:
        paths = set(zipped.namelist())
        assert ("ree/snapshot.tar.gz" in paths) == source_included
        assert ("ree/artifacts/runtime.tar" in paths) == runtime_included
        assert ("ree/results/data" in paths) == results_included
        assert not any(path.startswith("ree/workspace/") for path in paths)
