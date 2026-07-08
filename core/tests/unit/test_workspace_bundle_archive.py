import io
import json
import uuid
import zipfile

import pytest

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.storage.layout import ReeLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.storage.workspace_ops import (
    build_workspace_ree_archive,
    get_workspace,
    seal_workspace_ree,
)


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


def _read_metadata(layout):
    return json.loads(layout.metadata.read_text(encoding="utf-8"))


def test_bundle_archive_honors_inclusion_flags_and_manifest_remap(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "bundle-test")
    workspace_root = layout.workspace
    ree_root = layout.root

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    (workspace_root / "sbom.json").write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = _read_metadata(layout)
    metadata["reeIntent"] = {
        **(metadata.get("reeIntent") or {}),
        "runtime": "/runtime.tar.gz",
        "sbom": " sbom.json ",
    }
    metadata["reeSession"] = {
        **(metadata.get("reeSession") or {}),
        "source_snapshot_archive": "snapshot.tar.gz",
    }
    _write_metadata(layout, metadata)

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-01-01T00:00:00Z",
    )
    archive_bytes = build_workspace_ree_archive(storage_root, ree_id)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/snapshot.tar.gz" not in names
    assert "ree/artifacts/runtime.tar.gz" not in names
    assert "ree/artifacts/sbom.json" in names
    assert manifest["runtime"] == "runtime.tar.gz"
    assert manifest["sbom"] == "artifacts/sbom.json"
    assert manifest["source_included"] is False
    assert manifest["runtime_included"] is False


def test_bundle_archive_includes_snapshot_and_normalized_runtime_when_enabled(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "bundle-test")
    workspace_root = layout.workspace
    ree_root = layout.root

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    (workspace_root / "sbom.json").write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = _read_metadata(layout)
    metadata["reeIntent"] = {
        **(metadata.get("reeIntent") or {}),
        "runtime": "/runtime.tar.gz",
        "sbom": " sbom.json ",
    }
    metadata["reeSession"] = {
        **(metadata.get("reeSession") or {}),
        "source_snapshot_archive": " snapshot.tar.gz ",
    }
    _write_metadata(layout, metadata)

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=True,
        runtime_included=True,
        sealed_at="2026-01-01T00:00:00Z",
    )
    archive_bytes = build_workspace_ree_archive(storage_root, ree_id)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/snapshot.tar.gz" in names
    assert "ree/artifacts/runtime.tar.gz" in names
    assert "ree/artifacts/sbom.json" in names
    assert manifest["runtime"] == "artifacts/runtime.tar.gz"
    assert manifest["sbom"] == "artifacts/sbom.json"


def test_seal_persists_seal_facts_and_content_hash(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "seal-test")
    (layout.workspace / "test.py").write_text("print('hi')", encoding="utf-8")

    outputs = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T12:00:00Z",
    )

    assert outputs["sealedAt"] == "2026-06-05T12:00:00Z"
    assert outputs["sealHash"].startswith("sha256:")
    assert len(outputs["sealHash"]) == len("sha256:") + 64

    # Session persisted in metadata
    metadata = _read_metadata(layout)
    session = metadata["reeSession"]
    assert session["sealed_at"] == "2026-06-05T12:00:00Z"
    assert session["seal_hash"] == outputs["sealHash"]

    # sealed.zip written
    assert layout.sealed_archive.exists()

    # manifest.json reflects seal facts
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    assert manifest["sealed_at"] == "2026-06-05T12:00:00Z"
    assert manifest["seal_hash"] == outputs["sealHash"]

    # bundle contains manifest with matching seal_hash
    with zipfile.ZipFile(layout.sealed_archive) as zf:
        bundle_manifest = json.loads(zf.read("ree/ree.json"))
    assert bundle_manifest["seal_hash"] == outputs["sealHash"]


def test_seal_hash_is_stable_with_same_content(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "stable-hash-test")
    (layout.workspace / "code.py").write_text("x = 1", encoding="utf-8")

    out1 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T12:00:00Z",
    )
    out2 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T12:00:00Z",
    )
    assert out1["sealHash"] == out2["sealHash"]


def test_seal_hash_changes_with_different_content(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "content-hash-test")

    # Place the file in overlay/ so it ends up in the bundle entries.
    (layout.overlay / "code.py").write_text("x = 1", encoding="utf-8")
    out1 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T12:00:00Z",
    )

    (layout.overlay / "code.py").write_text("x = 2", encoding="utf-8")
    out2 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T12:00:00Z",
    )

    assert out1["sealHash"] != out2["sealHash"]


def test_build_archive_raises_before_seal(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, _ = _make_ree(storage_root, "unsealed")

    with pytest.raises(RuntimeError, match="not sealed"):
        build_workspace_ree_archive(storage_root, ree_id)


def test_get_workspace_tags_overlay_files_as_generated(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "provenance")

    # An upstream source file and an overlay recipe file both surface in the
    # merged workspace; only the overlay one is "generated".
    (layout.upstream / "main.py").write_text("print('hi')", encoding="utf-8")
    (layout.overlay / "build_runtime.sh").write_text("docker build .", encoding="utf-8")
    # Materialize the merged workspace the way the workbench would.
    (layout.workspace / "main.py").write_text("print('hi')", encoding="utf-8")
    (layout.workspace / "build_runtime.sh").write_text("docker build .", encoding="utf-8")

    files = {f["path"]: f["kind"] for f in get_workspace(storage_root, ree_id)["files"]}

    assert files["build_runtime.sh"] == "generated"
    assert files["main.py"] == "source"


def test_get_workspace_includes_draft_manifest_projection(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "draft-view")

    (layout.overlay / "build.sh").write_text("echo build", encoding="utf-8")
    (layout.artifacts / "runtime.tar.gz").write_bytes(b"runtime")
    (layout.workspace / "main.py").write_text("print('hi')", encoding="utf-8")

    workspace = get_workspace(storage_root, ree_id)
    draft = workspace["draftManifest"]

    assert draft["manifest_state"] == "draft"
    assert draft["ree_id"] == ree_id
    assert draft["name"] == "draft-view"
    assert draft["file_inventory"]["workspace"] == [{"path": "main.py", "kind": "source", "size": len("print('hi')")}]
    assert draft["file_inventory"]["overlay"] == [
        {"path": "overlay/build.sh", "kind": "ree", "tag": "Overlay", "size": len("echo build")}
    ]
    assert draft["file_inventory"]["artifacts"] == [
        {"path": "artifacts/runtime.tar.gz", "kind": "ree", "tag": "Archive", "size": len(b"runtime")}
    ]


def test_build_archive_returns_stored_bytes_after_seal(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "sealed-download")
    (layout.workspace / "run.sh").write_text("echo hi", encoding="utf-8")

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T00:00:00Z",
    )
    bytes1 = build_workspace_ree_archive(storage_root, ree_id)
    bytes2 = build_workspace_ree_archive(storage_root, ree_id)

    assert bytes1 == bytes2
    assert bytes1 == layout.sealed_archive.read_bytes()


def test_seal_records_consistency_and_bundles_receipts(tmp_path):
    """The motivating receipts scenario: build recorded, script edited, seal.

    The sealed manifest must carry a consistency block naming the build
    script as the moved input, and the run receipts must ride in the bundle
    under ree/receipts/.
    """
    from repo2ree_core.digests import digest_bytes
    from repo2ree_core.receipts import BuildRuntimeReceipt, record_receipt

    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "receipts-test")
    script = layout.workspace / "ree" / "build_script.sh"
    script.parent.mkdir(parents=True)
    script.write_text("make all", encoding="utf-8")

    def record_build(run_id, recorded_at, status="succeeded"):
        record_receipt(
            layout,
            BuildRuntimeReceipt(
                run_id=run_id,
                recorded_at=recorded_at,
                status=status,
                build_script_path="ree/build_script.sh",
                build_script_digest=digest_bytes(b"make all"),
            ),
            log=lambda *_: None,
        )

    # Only the latest successful build vouches for the endstate; the
    # superseded and failed runs stay in runs/ but out of the bundle.
    record_build("run-old", "2025-12-01T00:00:00Z")
    record_build("run-b", "2026-01-01T00:00:00Z")
    record_build("run-broken", "2026-02-01T00:00:00Z", status="failed")
    script.write_text("make other", encoding="utf-8")  # edit after the recorded build

    outputs = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        sealed_at="2026-06-05T00:00:00Z",
    )

    build_step = next(s for s in outputs["consistency"]["steps"] if s["step"] == "build_runtime")
    assert build_step["status"] == "stale"
    assert [entry["input"] for entry in build_step["staleInputs"]] == ["buildScript"]

    with zipfile.ZipFile(io.BytesIO(build_workspace_ree_archive(storage_root, ree_id))) as zf:
        bundle_manifest = json.loads(zf.read("ree/ree.json"))
        receipt = json.loads(zf.read("ree/receipts/run-b.receipt.json"))
        bundled_receipts = [n for n in zf.namelist() if n.startswith("ree/receipts/") and n.endswith(".json")]
    assert bundle_manifest["consistency"] == outputs["consistency"]
    assert receipt["runId"] == "run-b"
    assert bundled_receipts == ["ree/receipts/run-b.receipt.json"]
    # The full run history stays on the workbench.
    assert {p.name for p in layout.runs.glob("*.receipt.json")} == {
        "run-old.receipt.json",
        "run-b.receipt.json",
        "run-broken.receipt.json",
    }


def test_get_workspace_includes_live_consistency_report(tmp_path):
    """The workspace payload carries the same per-step freshness the seal
    records, so the UI flags staleness while authoring — before any seal."""
    from repo2ree_core.digests import digest_bytes
    from repo2ree_core.receipts import BuildRuntimeReceipt, record_receipt

    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "live-consistency")
    script = layout.workspace / "ree" / "build_script.sh"
    script.parent.mkdir(parents=True)
    script.write_text("make all", encoding="utf-8")
    record_receipt(
        layout,
        BuildRuntimeReceipt(
            run_id="run-b",
            recorded_at="2026-01-01T00:00:00Z",
            status="succeeded",
            build_script_path="ree/build_script.sh",
            build_script_digest=digest_bytes(b"make all"),
        ),
        log=lambda *_: None,
    )

    fresh = get_workspace(storage_root, ree_id)["consistency"]
    assert next(s for s in fresh["steps"] if s["step"] == "build_runtime")["status"] == "fresh"

    script.write_text("make other", encoding="utf-8")
    stale = get_workspace(storage_root, ree_id)["consistency"]
    build_step = next(s for s in stale["steps"] if s["step"] == "build_runtime")
    assert build_step["status"] == "stale"
    assert [entry["input"] for entry in build_step["staleInputs"]] == ["buildScript"]
