from datetime import UTC, datetime

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.model import WorkspaceMetadata
from repo2ree_core.reserved_paths import RESERVED_OVERLAY_SCRIPTS
from repo2ree_core.reserved_templates import reserved_script_template


def _make_metadata(ree_id: str = "ree-1", name: str = "demo") -> WorkspaceMetadata:
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return WorkspaceMetadata.model_validate(
        {
            "ree_id": ree_id,
            "name": name,
            "status": "draft",
            "created_at": ts,
            "updated_at": ts,
            "ree_intent": ReeIntent(name=name).model_dump(exclude_none=True),
            "ree_session": ReeSession().model_dump(exclude_none=True),
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


def test_creation_scripts_are_seeded_from_templates_and_materialized_to_workspace(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.ensure_reserved_overlay_scripts()

    assert {path.as_posix() for path in store.overlay.iter_files()} == set(RESERVED_OVERLAY_SCRIPTS)
    for path in RESERVED_OVERLAY_SCRIPTS:
        template = reserved_script_template(path)
        assert template.startswith("#!/usr/bin/env sh")
        assert store.overlay.read_text(path) == template
        assert store.workspace.read_text(path) == template
    assert store.exists() is True


def test_seeding_never_touches_authored_content(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.ensure_reserved_overlay_scripts()
    authored = "echo authored build\n"
    build_script = RESERVED_OVERLAY_SCRIPTS[0]
    store.overlay.write_text(build_script, authored)
    store.workspace.write_text(build_script, authored)

    store.ensure_reserved_overlay_scripts()

    assert store.overlay.read_text(build_script) == authored
    assert store.workspace.read_text(build_script) == authored


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
    assert "ree_id" in raw
    assert "created_at" in raw
    assert "ree_intent" in raw
    assert "ree_session" in raw


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
        "ree_id": "ree-1",
        "name": "demo",
        "status": "draft",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "ree_intent": {"name": "demo"},
        "ree_session": {},
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
    assert raw["ree_id"] == "ree-1"


def test_two_stores_for_different_rees_are_independent(tmp_path):
    a = ReeStore(ReeLayout.for_ree(tmp_path, "ree-a"))
    b = ReeStore(ReeLayout.for_ree(tmp_path, "ree-b"))

    a.ensure_dirs()
    a.write_metadata(_make_metadata(ree_id="ree-a", name="A"))

    assert a.exists() is True
    assert b.exists() is False
    assert a.read_metadata().name == "A"


def test_author_artifact_resolves_a_workspace_relative_path(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()
    store.workspace.write_text("runtime.tar", "bytes")

    assert store.author_artifact("runtime.tar") == store.layout.workspace / "runtime.tar"


def test_author_artifact_resolves_the_path_a_loaded_bundle_declares(tmp_path):
    """Packaging lifts the runtime into ``artifacts/`` and rewrites the declared
    path to match, so a loaded REE names a file that is not in its workspace."""
    store = _store(tmp_path)
    store.ensure_dirs()
    store.artifacts.write_text("runtime.tar", "bytes")

    assert store.author_artifact("artifacts/runtime.tar") == store.layout.artifacts / "runtime.tar"


def test_author_artifact_is_none_when_unset_or_absent(tmp_path):
    store = _store(tmp_path)
    store.ensure_dirs()

    assert store.author_artifact(None) is None
    assert store.author_artifact("") is None
    assert store.author_artifact("artifacts/missing.tar") is None
