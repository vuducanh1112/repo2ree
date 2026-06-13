import io
import json
import zipfile

from repo2ree_core.storage.review_ops import (
    complete_review_upload,
    init_review_upload,
    store_review_upload_bytes,
)


def _ree_archive_bytes(manifest: dict) -> bytes:  # type: ignore[type-arg]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ree/ree.json", json.dumps(manifest))
    return archive.getvalue()


def test_complete_review_upload_reads_packaging_facts_from_session_manifest_fields(
    tmp_path,
):
    storage_root = tmp_path / "reviews"
    upload = init_review_upload(storage_root, "demo.zip", 0, "application/zip")
    review_id = upload["reviewId"]
    token = upload["uploadToken"]
    archive_bytes = _ree_archive_bytes(
        {
            "ree_version": "1.0",
            "name": "demo",
            "origin_url": "https://example.org/repo.git",
            "source_type": "git",
            "runtime": "artifacts/runtime.tar.gz",
            "build_script": "scripts/build.sh",
            "activation_script": "scripts/activate.sh",
            "sbom": "artifacts/sbom.json",
            "hardware_description": {},
            "source_available": True,
            "source_acquired_by": "download",
            "source_snapshot_archive": "snapshot.tar.gz",
            "source_snapshot_captured_at": "2026-01-01T00:00:00Z",
            "source_included": True,
            "runtime_included": True,
        }
    )

    store_review_upload_bytes(storage_root, review_id, token, archive_bytes)
    result = complete_review_upload(storage_root, review_id, token, "demo.zip")
    review = result["review"]

    assert result["status"] == "ready"
    assert "packaging" not in review["reeIntent"]
    assert review["reeIntent"]["origin_url"] == "https://example.org/repo.git"
    assert review["reeSession"]["source_included"] is True
    assert review["reeSession"]["runtime_included"] is True
