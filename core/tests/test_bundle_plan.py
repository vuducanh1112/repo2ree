import io
import zipfile

from repo2ree_core.workspace.bundle import (
    ARTIFACTS_DIRNAME,
    REE_MANIFEST_ENTRY_PATH,
    REE_ROOT_PREFIX,
    build_zip_bytes,
    plan_artifact_layout,
    rewrite_manifest_for_bundle,
    safe_filename,
    should_include_snapshot,
)


def test_ree_root_prefix_and_manifest_path_constants():
    assert REE_ROOT_PREFIX == "ree/"
    assert REE_MANIFEST_ENTRY_PATH == "ree/ree.json"


def test_safe_filename_strips_path_separators():
    assert safe_filename("a/b/c.txt", "fallback") == "c.txt"
    assert safe_filename("a\\b\\c.txt", "fallback") == "c.txt"
    assert safe_filename("", "fallback") == "fallback"
    assert safe_filename(None, "fallback") == "fallback"
    assert safe_filename("   ", "fallback") == "fallback"


def test_build_zip_bytes_produces_valid_zip():
    entries = [
        ("ree/ree.json", b'{"name":"demo"}'),
        ("ree/overlay/recipe.sh", b"#!/bin/sh\n"),
    ]
    data = build_zip_bytes(entries)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.namelist() == ["ree/ree.json", "ree/overlay/recipe.sh"]
        assert zf.read("ree/ree.json") == b'{"name":"demo"}'


def test_snapshot_inclusion_requires_flag_and_snapshot_reference():
    assert should_include_snapshot(source_included=True, source_snapshot_archive="snapshot.tar.gz")
    assert not should_include_snapshot(source_included=False, source_snapshot_archive="snapshot.tar.gz")
    assert not should_include_snapshot(source_included=True, source_snapshot_archive="")


def test_plan_artifact_layout_skips_runtime_when_not_included():
    plan = plan_artifact_layout(
        on_disk_artifact_relpaths=[],
        workspace_runtime_path="runtime.tar.gz",
        workspace_sbom_path="sbom.json",
        workspace_files=frozenset({"runtime.tar.gz", "sbom.json"}),
        runtime_included=False,
    )

    assert dict(plan.workspace_pulls) == {"sbom.json": "sbom.json"}
    assert dict(plan.manifest_remap) == {"sbom.json": f"{ARTIFACTS_DIRNAME}/sbom.json"}


def test_plan_artifact_layout_normalizes_manifest_remap_keys():
    plan = plan_artifact_layout(
        on_disk_artifact_relpaths=[],
        workspace_runtime_path="/runtime.tar.gz",
        workspace_sbom_path="  sbom.json  ",
        workspace_files=frozenset({"runtime.tar.gz", "sbom.json"}),
        runtime_included=True,
    )

    assert dict(plan.workspace_pulls) == {
        "runtime.tar.gz": "runtime.tar.gz",
        "sbom.json": "sbom.json",
    }
    assert dict(plan.manifest_remap) == {
        "runtime.tar.gz": f"{ARTIFACTS_DIRNAME}/runtime.tar.gz",
        "sbom.json": f"{ARTIFACTS_DIRNAME}/sbom.json",
    }


def test_plan_artifact_layout_only_blocks_exact_archive_path_collisions():
    plan = plan_artifact_layout(
        on_disk_artifact_relpaths=["logs/runtime.tar.gz"],
        workspace_runtime_path="runtime.tar.gz",
        workspace_sbom_path="",
        workspace_files=frozenset({"runtime.tar.gz"}),
        runtime_included=True,
    )

    assert dict(plan.workspace_pulls) == {"runtime.tar.gz": "runtime.tar.gz"}


def test_rewrite_manifest_for_bundle_uses_normalized_paths():
    manifest = {"runtime": "runtime.tar.gz", "sbom": "sbom.json"}
    remap = {
        "runtime.tar.gz": f"{ARTIFACTS_DIRNAME}/runtime.tar.gz",
        "sbom.json": f"{ARTIFACTS_DIRNAME}/sbom.json",
    }

    rewritten = rewrite_manifest_for_bundle(manifest, remap)

    assert rewritten == {
        "runtime": f"{ARTIFACTS_DIRNAME}/runtime.tar.gz",
        "sbom": f"{ARTIFACTS_DIRNAME}/sbom.json",
    }
