import io
import json
import uuid
import zipfile

import pytest

from repo2ree_core.bundle.manifest import build_manifest_payload, split_manifest_payload
from repo2ree_core.bundle.restore import restore_ree_bundle
from repo2ree_core.bundle.seal import build_ree_archive, seal_ree
from repo2ree_core.domain.primitives import GitRevision, RunId
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt
from repo2ree_core.domain.ree.state import ReeLifecycleState, is_sealed
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.time_utils import parse_utc_instant


def _make_ree(storage_root, name):
    """Create an initialized, empty REE on disk and return (ree_id, layout)."""
    ree_id = uuid.uuid4().hex
    layout = ReeLayout.for_ree(storage_root, ree_id)
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_record_json(
        {
            "ree_id": ree_id,
            "external_ref": None,
            "name": name,
            "status": "ready",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "ree_intent": ReeIntent(name=name).model_dump(exclude_none=True),
            "ree_state": ReeLifecycleState().model_dump(exclude_none=True),
        }
    )
    return ree_id, layout


def _seed_author_ree(storage_root, name="author-ree"):
    """An REE carrying every kind of content a bundle publishes."""
    ree_id, layout = _make_ree(storage_root, name)
    store = ReeDirectory(layout)

    layout.snapshot_archive.write_bytes(b"snapshot-bytes")
    store.overlay.write_text("build.sh", "echo build\n")
    store.workspace.write_text("build.sh", "echo build\n")
    store.workspace.write_bytes("runtime.tar.gz", b"runtime-bytes")
    (layout.results_dir("exp-a") / "results").mkdir(parents=True)
    (layout.results_dir("exp-a") / "results" / "out.txt").write_text("baseline", encoding="utf-8")
    layout.author_operation_receipt("acquire_source").write_text(
        AcquireSourceReceipt(
            run_id=RunId("source-1"),
            started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            finished_at=parse_utc_instant("2026-01-01T00:00:01Z"),
            duration_ms=1000,
            recorded_at=parse_utc_instant("2026-01-01T00:00:01Z"),
            status="succeeded",
            origin_url="https://example.org/repo.git",
            source_type="git",
            revision=GitRevision("abc123"),
        ).model_dump_json(),
        encoding="utf-8",
    )

    metadata = json.loads(layout.record.read_text(encoding="utf-8"))
    metadata["ree_intent"] = {
        **metadata["ree_intent"],
        "origin_url": "https://example.org/repo.git",
        "source_type": "git",
        "revision": "abc123",
        "swhid": "swh:1:dir:deadbeef",
        "runtime": "runtime.tar.gz",
        "experiments": [{"name": "exp-a", "output_paths": ["results/out.txt"]}],
    }
    metadata["ree_state"] = {
        **metadata["ree_state"],
        "source_available": True,
        "source_acquired_by": "download",
        "source_snapshot_archive": "snapshot.tar.gz",
        "source_snapshot_digest": "sha256:1234",
    }
    layout.record.write_text(json.dumps(metadata), encoding="utf-8")
    return ree_id, layout


def _load_into_blank_ree(storage_root, archive_bytes, tmp_path, name="loaded-ree"):
    """Extract a bundle and restore it into a freshly created blank REE."""
    bundle_root, archive_path = _extract_bundle(archive_bytes, tmp_path)
    ree_id, layout = _make_ree(storage_root, name)
    outputs = restore_ree_bundle(
        storage_root,
        ree_id,
        bundle_root=bundle_root,
        archive_path=archive_path,
    )
    return outputs, layout


def _extract_bundle(archive_bytes, tmp_path):
    """Land a bundle on disk and extract it, the way the handler does."""
    stem = tmp_path / f"bundle-{uuid.uuid4().hex}"
    archive_path = stem.with_suffix(".zip")
    archive_path.write_bytes(archive_bytes)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        zf.extractall(stem)
    return stem, archive_path


def test_split_manifest_payload_inverts_build_manifest_payload():
    intent = ReeIntent(name="round-trip", origin_url="https://example.org/repo.git", source_type="git")
    session = ReeLifecycleState(source_available=True, source_acquired_by="download", dependency_level=2)

    payload = build_manifest_payload(intent, session, ree_id="abc123")
    recovered_intent, recovered_session = split_manifest_payload(payload)

    assert recovered_intent == intent
    # The manifest deliberately omits authoring detail, which comes back as defaults.
    assert recovered_session == session.model_copy(
        update={"detected_dependencies": None, "uploaded_archive": None, "source_resolved_commit": None}
    )


def test_split_manifest_payload_rejects_an_unknown_manifest_version():
    payload = build_manifest_payload(ReeIntent(), ReeLifecycleState(), ree_id="abc123")
    payload["ree_version"] = 99

    with pytest.raises(ValueError, match="unsupported manifest version"):
        split_manifest_payload(payload)


def test_loading_a_sealed_bundle_restores_intent_evidence_and_content(tmp_path):
    storage_root = tmp_path / "storage"
    author_id, _ = _seed_author_ree(storage_root)
    seal_ree(
        storage_root,
        author_id,
        source_included=True,
        runtime_included=True,
        results_included=True,
        sealed_at=parse_utc_instant("2026-01-02T00:00:00Z"),
    )
    archive_bytes = build_ree_archive(storage_root, author_id)

    outputs, layout = _load_into_blank_ree(storage_root, archive_bytes, tmp_path)
    store = ReeDirectory(layout)
    intent = store.read_intent()
    session = store.read_state()

    assert outputs.sealed is True
    assert outputs.source_restored is True
    assert intent.name == "author-ree"
    assert intent.origin_url == "https://example.org/repo.git"
    assert intent.swhid == "swh:1:dir:deadbeef"
    assert session.seal_hash is not None
    assert session.source_available is True

    assert layout.snapshot_archive.read_bytes() == b"snapshot-bytes"
    assert store.overlay.read_text("build.sh") == "echo build\n"
    assert (layout.artifacts / "runtime.tar.gz").read_bytes() == b"runtime-bytes"
    assert (layout.results_dir("exp-a") / "results" / "out.txt").read_text(encoding="utf-8") == "baseline"
    assert layout.author_operation_receipt("acquire_source").is_file()
    # The uploaded bytes are the sealed archive, so the load can hand back the
    # identical download; the manifest record comes with it.
    assert layout.sealed_archive.read_bytes() == archive_bytes
    assert store.read_manifest() is not None
    # The derived trees stay empty: the caller rebuilds them from the snapshot.
    assert store.upstream.list_files() == []


def test_loading_a_draft_bundle_leaves_the_ree_editable(tmp_path):
    storage_root = tmp_path / "storage"
    author_id, _ = _seed_author_ree(storage_root, name="draft-ree")
    archive_bytes = build_ree_archive(storage_root, author_id)

    outputs, layout = _load_into_blank_ree(storage_root, archive_bytes, tmp_path)
    session = ReeDirectory(layout).read_state()

    assert outputs.sealed is False
    assert is_sealed(session) is False
    assert layout.sealed_archive.exists() is False
    assert ReeDirectory(layout).read_manifest() is None
    assert outputs.source_restored is True
    assert outputs.overlay_files == 1


def test_loading_a_sourceless_bundle_clears_the_source_facts(tmp_path):
    storage_root = tmp_path / "storage"
    author_id, _ = _seed_author_ree(storage_root, name="sourceless-ree")
    seal_ree(
        storage_root,
        author_id,
        source_included=False,
        runtime_included=True,
        results_included=False,
        sealed_at=parse_utc_instant("2026-01-02T00:00:00Z"),
    )
    archive_bytes = build_ree_archive(storage_root, author_id)

    outputs, layout = _load_into_blank_ree(storage_root, archive_bytes, tmp_path)
    store = ReeDirectory(layout)

    assert outputs.source_restored is False
    assert layout.snapshot_archive.exists() is False
    session = store.read_state()
    assert session.source_available is False
    assert session.source_snapshot_archive is None
    # The origin survives on the intent, so the source is still acquirable.
    assert store.read_intent().origin_url == "https://example.org/repo.git"


def test_loading_replaces_whatever_the_target_ree_held(tmp_path):
    storage_root = tmp_path / "storage"
    author_id, _ = _seed_author_ree(storage_root)
    archive_bytes = build_ree_archive(storage_root, author_id)

    target_id, target_layout = _make_ree(storage_root, "occupied")
    target_store = ReeDirectory(target_layout)
    target_store.overlay.write_text("stale.txt", "old")
    target_store.artifacts.write_bytes("stale.bin", b"old")
    (target_layout.results_dir("gone") / "out.txt").parent.mkdir(parents=True, exist_ok=True)
    (target_layout.results_dir("gone") / "out.txt").write_text("old", encoding="utf-8")

    bundle_root, archive_path = _extract_bundle(archive_bytes, tmp_path)
    restore_ree_bundle(storage_root, target_id, bundle_root=bundle_root, archive_path=archive_path)

    assert target_store.overlay.exists("stale.txt") is False
    assert target_store.artifacts.exists("stale.bin") is False
    assert (target_layout.results_dir("gone") / "out.txt").exists() is False
    assert target_store.read_intent().name == "author-ree"


def test_restoring_something_that_is_not_a_bundle_is_rejected(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, _ = _make_ree(storage_root, "target")
    not_a_bundle = tmp_path / "not-a-bundle"
    (not_a_bundle / "src").mkdir(parents=True)

    with pytest.raises(ValueError, match="not an REE bundle"):
        restore_ree_bundle(storage_root, ree_id, bundle_root=not_a_bundle, archive_path=tmp_path / "none.zip")
