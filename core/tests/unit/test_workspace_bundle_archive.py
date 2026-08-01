import io
import json
import uuid
import zipfile

import pytest

from repo2ree_core.bundle.seal import build_workspace_ree_archive, seal_workspace_ree
from repo2ree_core.domain.primitives import RunId, ScriptPath
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.operations.workspace_view import get_workspace
from repo2ree_core.ree.layout import SBOM_ARTIFACT_PATH, ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.time_utils import parse_utc_instant


def _make_ree(storage_root, name):
    """Create an initialized REE on disk and return (ree_id, layout)."""
    ree_id = uuid.uuid4().hex
    layout = ReeLayout.for_ree(storage_root, ree_id)
    store = ReeStore(layout)
    store.ensure_dirs()
    store.write_metadata_json(
        {
            "ree_id": ree_id,
            "external_ref": None,
            "name": name,
            "status": "ready",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "ree_intent": ReeIntent(name=name).model_dump(exclude_none=True),
            "ree_session": ReeSession().model_dump(exclude_none=True),
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
    layout.sbom.write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = _read_metadata(layout)
    metadata["ree_intent"] = {
        **(metadata.get("ree_intent") or {}),
        "runtime": "/runtime.tar.gz",
        "sbom": SBOM_ARTIFACT_PATH,
    }
    metadata["ree_session"] = {
        **(metadata.get("ree_session") or {}),
        "source_snapshot_archive": "snapshot.tar.gz",
    }
    _write_metadata(layout, metadata)

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=parse_utc_instant("2026-01-01T00:00:00Z"),
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


def _seed_results_experiments(layout):
    """Two experiments with captured result stores, declared on the intent."""
    for name in ("exp-a", "exp-b"):
        (layout.results_dir(name) / "results").mkdir(parents=True)
        (layout.results_dir(name) / "results" / "out.txt").write_text(name, encoding="utf-8")
    metadata = _read_metadata(layout)
    metadata["ree_intent"] = {
        **(metadata.get("ree_intent") or {}),
        "experiments": [
            {"name": "exp-a", "output_paths": ["results/out.txt"]},
            {"name": "exp-b", "output_paths": ["results/out.txt"]},
        ],
    }
    _write_metadata(layout, metadata)


def test_bundle_seals_all_results_when_results_included(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "results-in")
    _seed_results_experiments(layout)

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=True,
        sealed_at=parse_utc_instant("2026-01-01T00:00:00Z"),
    )
    with zipfile.ZipFile(io.BytesIO(build_workspace_ree_archive(storage_root, ree_id))) as zf:
        names = zf.namelist()

    assert "ree/results/exp-a/results/out.txt" in names
    assert "ree/results/exp-b/results/out.txt" in names


def test_bundle_omits_results_when_not_included(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "results-out")
    _seed_results_experiments(layout)

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=parse_utc_instant("2026-01-01T00:00:00Z"),
    )
    with zipfile.ZipFile(io.BytesIO(build_workspace_ree_archive(storage_root, ree_id))) as zf:
        names = zf.namelist()

    assert not any(n.startswith("ree/results/") for n in names)


def test_bundle_archive_includes_snapshot_and_normalized_runtime_when_enabled(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "bundle-test")
    workspace_root = layout.workspace
    ree_root = layout.root

    (workspace_root / "runtime.tar.gz").write_bytes(b"runtime-bytes")
    layout.sbom.write_text('{"bom":1}', encoding="utf-8")
    (ree_root / "snapshot.tar.gz").write_bytes(b"snapshot-bytes")

    metadata = _read_metadata(layout)
    metadata["ree_intent"] = {
        **(metadata.get("ree_intent") or {}),
        "runtime": "/runtime.tar.gz",
        "sbom": SBOM_ARTIFACT_PATH,
    }
    metadata["ree_session"] = {
        **(metadata.get("ree_session") or {}),
        "source_snapshot_archive": " snapshot.tar.gz ",
    }
    _write_metadata(layout, metadata)

    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=True,
        runtime_included=True,
        results_included=False,
        sealed_at=parse_utc_instant("2026-01-01T00:00:00Z"),
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
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T12:00:00Z"),
    )

    assert outputs.sealed_at == parse_utc_instant("2026-06-05T12:00:00Z")
    assert outputs.seal_hash is not None
    assert outputs.seal_hash.startswith("sha256:")
    assert len(outputs.seal_hash) == len("sha256:") + 64

    # Session persisted in metadata
    metadata = _read_metadata(layout)
    session = metadata["ree_session"]
    assert session["sealed_at"] == "2026-06-05T12:00:00Z"
    assert session["seal_hash"] == outputs.seal_hash

    # sealed.zip written
    assert layout.sealed_archive.exists()

    # manifest.json reflects seal facts
    manifest = json.loads(layout.manifest.read_text(encoding="utf-8"))
    assert manifest["sealed_at"] == "2026-06-05T12:00:00Z"
    assert manifest["seal_hash"] == outputs.seal_hash

    # bundle contains manifest with matching seal_hash
    with zipfile.ZipFile(layout.sealed_archive) as zf:
        bundle_manifest = json.loads(zf.read("ree/ree.json"))
    assert bundle_manifest["seal_hash"] == outputs.seal_hash


def test_seal_hash_is_stable_with_same_content(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "stable-hash-test")
    (layout.workspace / "code.py").write_text("x = 1", encoding="utf-8")

    out1 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T12:00:00Z"),
    )
    out2 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T12:00:00Z"),
    )
    assert out1.seal_hash == out2.seal_hash


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
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T12:00:00Z"),
    )

    (layout.overlay / "code.py").write_text("x = 2", encoding="utf-8")
    out2 = seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T12:00:00Z"),
    )

    assert out1.seal_hash != out2.seal_hash


def test_build_archive_assembles_a_draft_bundle_before_seal(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "unsealed")
    (layout.overlay / "build.sh").write_text("echo build", encoding="utf-8")

    with zipfile.ZipFile(io.BytesIO(build_workspace_ree_archive(storage_root, ree_id))) as zf:
        names = zf.namelist()
        manifest = json.loads(zf.read("ree/ree.json"))

    assert "ree/overlay/build.sh" in names
    # A draft carries no seal stamps: it is a handoff, not a citable artifact.
    assert manifest["sealed_at"] is None
    assert manifest["seal_hash"] is None


def test_build_archive_raises_when_the_sealed_archive_is_missing(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "sealed-then-lost")
    seal_workspace_ree(
        storage_root,
        ree_id,
        source_included=False,
        runtime_included=False,
        results_included=False,
        sealed_at=parse_utc_instant("2026-01-01T00:00:00Z"),
    )
    layout.sealed_archive.unlink()

    with pytest.raises(RuntimeError, match="re-seal"):
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

    files = {f.path: f.kind for f in get_workspace(storage_root, ree_id).files}

    assert files["build_runtime.sh"] == "generated"
    assert files["main.py"] == "source"


def test_get_workspace_includes_draft_manifest_projection(tmp_path):
    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "draft-view")

    (layout.overlay / "build.sh").write_text("echo build", encoding="utf-8")
    (layout.artifacts / "runtime.tar.gz").write_bytes(b"runtime")
    (layout.workspace / "main.py").write_text("print('hi')", encoding="utf-8")

    workspace = get_workspace(storage_root, ree_id)
    draft = workspace.draft_manifest

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
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T00:00:00Z"),
    )
    bytes1 = build_workspace_ree_archive(storage_root, ree_id)
    bytes2 = build_workspace_ree_archive(storage_root, ree_id)

    assert bytes1 == bytes2
    assert bytes1 == layout.sealed_archive.read_bytes()


def test_seal_records_consistency_and_bundles_receipts(tmp_path):
    """The motivating receipts scenario: build recorded, script edited, seal.

    The sealed manifest must carry a consistency block naming the build
    script as the moved input, and the selected author receipts must ride in
    the bundle under ree/receipts/author/.
    """
    from repo2ree_core.digests import digest_bytes
    from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt
    from repo2ree_core.evidence.receipts.store import record_receipt

    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "receipts-test")
    script = layout.workspace / "ree-scripts" / "build_script.sh"
    script.parent.mkdir(parents=True)
    script.write_text("make all", encoding="utf-8")

    def record_build(run_id, recorded_at, status="succeeded"):
        record_receipt(
            layout,
            BuildRuntimeReceipt(
                run_id=run_id,
                started_at=recorded_at,
                finished_at=recorded_at,
                duration_ms=0,
                recorded_at=recorded_at,
                status=status,
                build_script_path=ScriptPath("ree-scripts/build_script.sh"),
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
        results_included=False,
        sealed_at=parse_utc_instant("2026-06-05T00:00:00Z"),
    )

    build_step = next(s for s in outputs.consistency.steps if s.step == "build_runtime")
    assert build_step.status == "stale"
    assert [entry.input for entry in build_step.stale_inputs] == ["build_script"]

    with zipfile.ZipFile(io.BytesIO(build_workspace_ree_archive(storage_root, ree_id))) as zf:
        bundle_manifest = json.loads(zf.read("ree/ree.json"))
        receipt = json.loads(zf.read("ree/receipts/author/build_runtime.json"))
        bundled_receipts = [n for n in zf.namelist() if n.startswith("ree/receipts/") and n.endswith(".json")]
    assert bundle_manifest["consistency"] == outputs.consistency.model_dump(mode="json")
    assert receipt["run_id"] == "run-b"
    assert bundled_receipts == ["ree/receipts/author/build_runtime.json"]
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
    from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt
    from repo2ree_core.evidence.receipts.store import record_receipt

    storage_root = tmp_path / "storage"
    ree_id, layout = _make_ree(storage_root, "live-consistency")
    script = layout.workspace / "ree-scripts" / "build_script.sh"
    script.parent.mkdir(parents=True)
    script.write_text("make all", encoding="utf-8")
    record_receipt(
        layout,
        BuildRuntimeReceipt(
            run_id=RunId("run-b"),
            started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            finished_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            duration_ms=0,
            recorded_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            status="succeeded",
            build_script_path=ScriptPath("ree-scripts/build_script.sh"),
            build_script_digest=digest_bytes(b"make all"),
        ),
        log=lambda *_: None,
    )

    fresh = get_workspace(storage_root, ree_id).consistency.model_dump()
    assert next(s for s in fresh["steps"] if s["step"] == "build_runtime")["status"] == "fresh"

    script.write_text("make other", encoding="utf-8")
    stale = get_workspace(storage_root, ree_id).consistency.model_dump()
    build_step = next(s for s in stale["steps"] if s["step"] == "build_runtime")
    assert build_step["status"] == "stale"
    assert [entry["input"] for entry in build_step["stale_inputs"]] == ["build_script"]
