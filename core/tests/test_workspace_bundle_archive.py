import io
import json
import zipfile

from repo2ree_core.storage.workspace_ops import (
    build_workspace_ree_archive,
    create_workspace,
    metadata_path,
    workspace_dir,
)


def _write_metadata(storage_root, ree_id, metadata):
    metadata_path(storage_root, ree_id).write_text(
        json.dumps(metadata), encoding="utf-8"
    )


def test_bundle_archive_honors_inclusion_flags_and_manifest_remap(tmp_path):
    storage_root = tmp_path / "storage"
    workspace = create_workspace(storage_root, source_mode="demo", name="bundle-test")
    ree_id = workspace["reeId"]
    workspace_root = workspace_dir(storage_root, ree_id)
    ree_root = workspace_root.parent

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    (workspace_root / "sbom.json").write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = json.loads(
        metadata_path(storage_root, ree_id).read_text(encoding="utf-8")
    )
    metadata["reeDraft"] = {
        **(metadata.get("reeDraft") or {}),
        "runtime": "/runtime.tar.gz",
        "runtime_included": False,
        "sbom": " sbom.json ",
        "source_included": False,
        "source_snapshot_archive": "snapshot.tar.gz",
    }
    _write_metadata(storage_root, ree_id, metadata)

    archive_bytes = build_workspace_ree_archive(storage_root, ree_id)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/snapshot.tar.gz" not in names
    assert "ree/artifacts/runtime.tar.gz" not in names
    assert "ree/artifacts/sbom.json" in names
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["sbom"] == "artifacts/sbom.json"

    updated_metadata = json.loads(
        metadata_path(storage_root, ree_id).read_text(encoding="utf-8")
    )
    assert updated_metadata["reeDraft"]["downloadable_files"] == names


def test_bundle_archive_includes_snapshot_and_normalized_runtime_when_enabled(tmp_path):
    storage_root = tmp_path / "storage"
    workspace = create_workspace(storage_root, source_mode="demo", name="bundle-test")
    ree_id = workspace["reeId"]
    workspace_root = workspace_dir(storage_root, ree_id)
    ree_root = workspace_root.parent

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    (workspace_root / "sbom.json").write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = json.loads(
        metadata_path(storage_root, ree_id).read_text(encoding="utf-8")
    )
    metadata["reeDraft"] = {
        **(metadata.get("reeDraft") or {}),
        "runtime": "/runtime.tar.gz",
        "runtime_included": True,
        "sbom": " sbom.json ",
        "source_included": True,
        "source_snapshot_archive": " snapshot.tar.gz ",
    }
    _write_metadata(storage_root, ree_id, metadata)

    archive_bytes = build_workspace_ree_archive(storage_root, ree_id)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/snapshot.tar.gz" in names
    assert "ree/artifacts/runtime.tar.gz" in names
    assert "ree/artifacts/sbom.json" in names
    assert manifest["runtime"] == "artifacts/runtime.tar.gz"
    assert manifest["sbom"] == "artifacts/sbom.json"
