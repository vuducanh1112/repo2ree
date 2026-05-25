from datetime import datetime, timezone

import pytest

from repo2ree_core.domain.ree import REE
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.model import WorkspaceMetadata


def _make_metadata(ree_id: str = "ree-1", name: str = "demo") -> WorkspaceMetadata:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return WorkspaceMetadata.model_validate(
        {
            "reeId": ree_id,
            "name": name,
            "status": "draft",
            "createdAt": ts,
            "updatedAt": ts,
            "reeDraft": REE(name=name).model_dump(exclude_none=True),
        }
    )


def _store(tmp_path) -> ReeStore:
    layout = ReeLayout.for_ree(tmp_path, "ree-1")
    return ReeStore(layout)


def test_exists_false_before_ensure_dirs(tmp_path):
    store = _store(tmp_path)
    assert store.exists() is False


def test_ensure_dirs_creates_root_and_workspace(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    assert store.layout.root.is_dir()
    assert store.layout.workspace.is_dir()
    assert store.exists() is True


def test_ensure_dirs_is_idempotent(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.ensure_dirs()
    assert store.layout.root.is_dir()


def test_metadata_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    original = _make_metadata()

    assert store.metadata_exists() is False
    store.write_metadata(original)
    assert store.metadata_exists() is True

    read_back = store.read_metadata()
    assert read_back.ree_id == original.ree_id
    assert read_back.name == original.name
    assert read_back.status == original.status


def test_ree_accepts_legacy_single_reproducibility_level():
    ree = REE.model_validate({"name": "demo", "eval_level": 6, "repro_level": "L6"})

    assert ree.dependency_level == 3
    assert ree.environment_level == 2
    assert ree.machine_level == 0


def test_read_metadata_raises_when_absent(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    with pytest.raises(FileNotFoundError):
        store.read_metadata()


def test_write_metadata_uses_aliased_keys_on_disk(tmp_path):
    import json

    store = _store(tmp_path)
    store.ensure_dirs()
    store.write_metadata(_make_metadata())

    raw = json.loads(store.layout.metadata.read_text(encoding="utf-8"))
    assert "reeId" in raw
    assert "createdAt" in raw
    assert "reeDraft" in raw


def test_write_metadata_creates_parent_if_missing(tmp_path):
    store = _store(tmp_path)
    store.write_metadata(_make_metadata())
    assert store.layout.metadata.is_file()


def test_manifest_roundtrip(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()

    assert store.read_manifest() is None

    payload = {"name": "demo", "runtime": "build.sh", "version": "1"}
    store.write_manifest(payload)

    assert store.read_manifest() == payload


def test_manifest_written_with_stable_key_order(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.write_manifest({"b": 2, "a": 1})

    text = store.layout.manifest.read_text(encoding="utf-8")
    assert text.index('"a"') < text.index('"b"')


def test_atomic_write_leaves_no_tmp_files_after_success(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.write_metadata(_make_metadata())

    leftovers = [p for p in store.layout.root.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_remove_deletes_entire_tree(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.write_metadata(_make_metadata())
    assert store.exists()

    store.remove()
    assert store.exists() is False
    assert not store.layout.metadata.exists()


def test_remove_is_noop_when_absent(tmp_path):
    store = _store(tmp_path)
    store.remove()  # must not raise
    assert store.exists() is False


def test_metadata_json_roundtrip_preserves_extra_fields(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()

    payload = {
        "reeId": "ree-1",
        "name": "demo",
        "status": "draft",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "reeDraft": {"name": "demo"},
        "vendorExtraField": {"nested": [1, 2, 3]},
    }
    store.write_metadata_json(payload)
    assert store.read_metadata_json() == payload


def test_write_metadata_json_is_atomic(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.write_metadata_json({"a": 1})
    store.write_metadata_json({"a": 2})

    leftovers = [p for p in store.layout.root.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
    assert store.read_metadata_json() == {"a": 2}


def test_typed_write_metadata_uses_atomic_json_path(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.write_metadata(_make_metadata())

    raw = store.read_metadata_json()
    assert raw["reeId"] == "ree-1"


def test_two_stores_for_different_rees_are_independent(tmp_path):
    a = ReeStore(ReeLayout.for_ree(tmp_path, "ree-a"))
    b = ReeStore(ReeLayout.for_ree(tmp_path, "ree-b"))

    a.ensure_dirs()
    a.write_metadata(_make_metadata(ree_id="ree-a", name="A"))

    assert a.exists() is True
    assert b.exists() is False
    assert a.read_metadata().name == "A"
