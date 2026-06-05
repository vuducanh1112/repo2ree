import io
import json
import uuid
import zipfile

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.storage.workspace_ops import build_workspace_ree_archive


def _make_ree(storage_root, name):
    """Create an initialized REE on disk and return (ree_id, layout)."""
    ree_id = uuid.uuid4().hex
    layout = ReeLayout.for_ree(storage_root, ree_id)
    store = ReeStore(layout)
    store.ensure_dirs()
    store.write_metadata_json(
        {
            "reeId": ree_id,
            "externalRef": None,
            "name": name,
            "status": "ready",
            "reeIntent": ReeIntent(name=name).model_dump(exclude_none=True),
            "reeSession": ReeSession().model_dump(exclude_none=True),
            "source": {"mode": "download", "acquiredAt": "2026-01-01T00:00:00Z"},
        }
    )
    return ree_id, layout


def _write_metadata(layout, metadata):
    layout.metadata.write_text(json.dumps(metadata), encoding="utf-8")


def test_bundle_archive_honors_inclusion_flags_and_manifest_remap(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "bundle-test")
    workspace_root = layout.workspace
    ree_root = layout.root

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    (workspace_root / "sbom.json").write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = json.loads(layout.metadata.read_text(encoding="utf-8"))
    metadata["reeIntent"] = {
        **(metadata.get("reeIntent") or {}),
        "runtime": "/runtime.tar.gz",
        "sbom": " sbom.json ",
        "packaging": {"source_included": False, "runtime_included": False},
    }
    metadata["reeSession"] = {
        **(metadata.get("reeSession") or {}),
        "source_snapshot_archive": "snapshot.tar.gz",
    }
    _write_metadata(layout, metadata)

    archive_bytes = build_workspace_ree_archive(storage_root, ree_id)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/snapshot.tar.gz" not in names
    assert "ree/artifacts/runtime.tar.gz" not in names
    assert "ree/artifacts/sbom.json" in names
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["sbom"] == "artifacts/sbom.json"

    updated_metadata = json.loads(layout.metadata.read_text(encoding="utf-8"))
    assert updated_metadata["reeSession"]["downloadable_files"] == names


def test_bundle_archive_includes_snapshot_and_normalized_runtime_when_enabled(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "bundle-test")
    workspace_root = layout.workspace
    ree_root = layout.root

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    (workspace_root / "sbom.json").write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = json.loads(layout.metadata.read_text(encoding="utf-8"))
    metadata["reeIntent"] = {
        **(metadata.get("reeIntent") or {}),
        "runtime": "/runtime.tar.gz",
        "sbom": " sbom.json ",
        "packaging": {"source_included": True, "runtime_included": True},
    }
    metadata["reeSession"] = {
        **(metadata.get("reeSession") or {}),
        "source_snapshot_archive": " snapshot.tar.gz ",
    }
    _write_metadata(layout, metadata)

    archive_bytes = build_workspace_ree_archive(storage_root, ree_id)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/snapshot.tar.gz" in names
    assert "ree/artifacts/runtime.tar.gz" in names
    assert "ree/artifacts/sbom.json" in names
    assert manifest["runtime"] == "artifacts/runtime.tar.gz"
    assert manifest["sbom"] == "artifacts/sbom.json"
