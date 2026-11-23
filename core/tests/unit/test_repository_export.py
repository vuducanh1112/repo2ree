import json
import subprocess
import zipfile

import pytest
from recorded_ree import as_recorded

from repo2ree_core.bundle.download import materialized_ree_download
from repo2ree_core.bundle.repository_restore import restore_repository
from repo2ree_core.digests import digest_file
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.lfs import LfsPointer
from repo2ree_core.persistence.operation_history import read_operation_history
from repo2ree_protocol.command import (
    LoadReeBundleArgs,
    LoadReeBundleCommand,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    SealReeArgs,
    SealReeCommand,
)
from repo2ree_protocol.tools import find_tool
from repo2ree_ree.model import CapturePolicy


def _sealed(tmp_path, monkeypatch):
    layout = ReeLayout(root=tmp_path / "author")
    initialize_ree(layout, name="offline")
    (layout.results / "experiment").mkdir(parents=True)
    payload = b"binary\0result" * 4096
    (layout.results / "experiment/data.bin").write_bytes(payload)
    as_recorded(layout)
    result = run_command(
        SealReeCommand(
            args=SealReeArgs(
                source_included=False,
                experiment_environment_included=False,
                results_included=True,
            )
        ),
        log=lambda *args: None,
        layout=layout,
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
    destination.upload_staging_file("offline").write_bytes(data)
    loaded = run_command(
        LoadReeBundleCommand(
            args=LoadReeBundleArgs(
                upload_token="offline",  # noqa: S106
                archive_name="ree.zip",
            )
        ),
        log=lambda *args: None,
        layout=destination,
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
    store.write_ree(
        ree.model_copy(update={"seal": None, "subject": ree.subject.model_copy(update={"capture": CapturePolicy()})})
    )
    as_recorded(layout)
    renamed = run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "reselected"})),
        log=lambda *args: None,
        layout=layout,
    )
    assert renamed.status == "succeeded", renamed
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
@pytest.mark.parametrize("experiment_environment_included", [False, True])
@pytest.mark.parametrize("results_included", [False, True])
def test_seal_toggles_are_the_only_optional_payload_selection(
    tmp_path,
    monkeypatch,
    source_included,
    experiment_environment_included,
    results_included,
):
    layout = ReeLayout(root=tmp_path / "author")
    initialize_ree(layout, name="selection")
    store = ReeDirectory(layout)
    ree = store.read_ree()
    definition = ree.subject.definition
    assert definition.experiment_environment is not None
    experiment_environment = definition.experiment_environment.model_copy(update={"artifact_path": "runtime.tar"})
    store.write_ree(
        ree.model_copy(
            update={
                "subject": ree.subject.model_copy(
                    update={
                        "definition": definition.model_copy(update={"experiment_environment": experiment_environment})
                    }
                )
            }
        )
    )
    layout.snapshot_archive.write_bytes(b"source")
    layout.kept_environment("runtime.tar").parent.mkdir(parents=True, exist_ok=True)
    layout.kept_environment("runtime.tar").write_bytes(b"experiment_environment")
    layout.results.mkdir(exist_ok=True)
    (layout.results / "data").write_bytes(b"result")
    as_recorded(layout)
    result = run_command(
        SealReeCommand(
            args=SealReeArgs(
                source_included=source_included,
                experiment_environment_included=experiment_environment_included,
                results_included=results_included,
            )
        ),
        log=lambda *args: None,
        layout=layout,
    )
    assert result.status == "succeeded", result
    with materialized_ree_download(layout) as archive, zipfile.ZipFile(archive) as zipped:
        paths = set(zipped.namelist())
        assert ("ree/snapshot.tar.gz" in paths) == source_included
        assert ("ree/artifacts/runtime.tar" in paths) == experiment_environment_included
        assert ("ree/results/data" in paths) == results_included
        assert not any(path.startswith("ree/workspace/") for path in paths)


def test_a_loaded_sealed_ree_holds_exactly_the_files_its_seal_lists(tmp_path, monkeypatch):
    layout, _pointer, _payload = _sealed(tmp_path, monkeypatch)
    with materialized_ree_download(layout) as archive:
        data = archive.read_bytes()
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="blank")
    destination.acquire_script.write_bytes(b"#!/bin/sh\n# the blank REE's own\n")
    destination.materialize_marker.write_text("{}")
    as_recorded(destination)
    destination.upload_staging_file("offline").write_bytes(data)
    loaded = run_command(
        LoadReeBundleCommand(args=LoadReeBundleArgs(upload_token="offline", archive_name="ree.zip")),  # noqa: S106
        log=lambda *args: None,
        layout=destination,
    )
    assert loaded.status == "succeeded", loaded
    sealed = ReeDirectory(destination).read_ree()
    assert sealed.seal is not None
    listed = {str(entry.path): entry.digest for entry in sealed.subject.contents.entries}
    for path in (destination.acquire_script, destination.materialize_script, destination.materialize_marker):
        relative = path.relative_to(destination.root).as_posix()
        if relative in listed:
            assert digest_file(path) == listed[relative], relative
        else:
            assert not path.exists(), relative


def test_a_record_kept_beside_the_history_travels_as_the_exporting_ree_s(tmp_path):
    author = ReeLayout(root=tmp_path / "author")
    initialize_ree(author, name="drifted")
    patched = run_command(
        PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "patched"})),
        log=lambda *args: None,
        layout=author,
    )
    assert patched.status == "succeeded"
    with open_history(author) as history:
        left = history.git("rev-parse", "refs/heads/ree-history").stdout.decode().strip()
        earlier = history.git("rev-parse", f"{left}^").stdout.decode().strip()
        history.git("update-ref", "refs/heads/ree-history", earlier)
    refused = run_command(SealReeCommand(args=SealReeArgs()), log=lambda *args: None, layout=author)
    assert refused.history is not None
    assert refused.history.capture_status == "failed"
    with open_history(author) as history:
        history.git("update-ref", "refs/heads/ree-history", left)
    sealed = run_command(SealReeCommand(args=SealReeArgs()), log=lambda *args: None, layout=author)
    assert sealed.status == "succeeded", sealed
    with materialized_ree_download(author) as archive:
        data = archive.read_bytes()
    destination = ReeLayout(root=tmp_path / "destination")
    initialize_ree(destination, name="blank")
    destination.upload_staging_file("offline").write_bytes(data)
    loaded = run_command(
        LoadReeBundleCommand(args=LoadReeBundleArgs(upload_token="offline", archive_name="ree.zip")),  # noqa: S106
        log=lambda *args: None,
        layout=destination,
    )

    assert loaded.status == "succeeded", loaded
    attempt = refused.history.attempt_id
    assert not (destination.git_dir / "repo2ree" / "operations" / f"{attempt}.json").exists()
    assert list((destination.git_dir / "repo2ree" / "imports").glob(f"*/operations/{attempt}.json"))
    assert attempt in {record.attempt_id for record in read_operation_history(destination).operations}
