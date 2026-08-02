import dataclasses
from pathlib import Path

import pytest

from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.persistence.layout import ReeLayout, validate_upload_token


def test_for_ree_composes_root_from_storage_root_and_id():
    layout = ReeLayout.for_ree("/var/lib/repo2ree", "abc123")
    assert layout.root == Path("/var/lib/repo2ree/abc123")


def test_for_ree_accepts_path_storage_root():
    layout = ReeLayout.for_ree(Path("/var/lib/repo2ree"), "abc123")
    assert layout.root == Path("/var/lib/repo2ree/abc123")


def test_top_level_paths_are_derived_from_root():
    layout = ReeLayout.for_ree("/r", "ree1")
    assert layout.record == Path("/r/ree1/.ree.json")
    assert layout.manifest == Path("/r/ree1/manifest.json")
    assert layout.snapshot_archive == Path("/r/ree1/snapshot.tar.gz")
    assert layout.upload_staging == Path("/r/ree1/upload-staging")
    assert layout.upstream == Path("/r/ree1/upstream")
    assert layout.overlay == Path("/r/ree1/overlay")
    assert layout.artifacts == Path("/r/ree1/artifacts")
    assert layout.workspace == Path("/r/ree1/workspace")


def test_relative_resolvers_join_under_their_subtree():
    layout = ReeLayout.for_ree("/r", "ree1")
    assert layout.upstream_file("src/main.py") == Path("/r/ree1/upstream/src/main.py")
    assert layout.overlay_file("Dockerfile") == Path("/r/ree1/overlay/Dockerfile")
    assert layout.artifact_file("runtime.tar.gz") == Path("/r/ree1/artifacts/runtime.tar.gz")
    assert layout.workspace_file("build.sh") == Path("/r/ree1/workspace/build.sh")


def test_upload_staging_file_uses_token_as_filename():
    layout = ReeLayout.for_ree("/r", "ree1")
    assert layout.upload_staging_file("tok42") == Path("/r/ree1/upload-staging/tok42.bin")


def test_layout_is_frozen():
    layout = ReeLayout.for_ree("/r", "ree1")
    with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
        layout.root = Path("/elsewhere")  # type: ignore[misc]


def test_layout_value_equality():
    a = ReeLayout.for_ree("/r", "ree1")
    b = ReeLayout.for_ree("/r", "ree1")
    c = ReeLayout.for_ree("/r", "ree2")
    assert a == b
    assert a != c


@pytest.mark.parametrize(
    "bad",
    [
        "/etc/passwd",
        "../escape",
        "nested/../escape",
        "",
    ],
)
def test_validate_relative_path_rejects_unsafe_inputs(bad):
    with pytest.raises(ValueError):
        validate_relative_path(bad)


def test_validate_relative_path_accepts_normal_relative():
    validate_relative_path("src/main.py")
    validate_relative_path("Dockerfile")
    validate_relative_path("a/b/c.txt")


def test_resolvers_reject_absolute_paths():
    layout = ReeLayout.for_ree("/r", "ree1")
    with pytest.raises(ValueError):
        layout.overlay_file("/etc/passwd")


def test_resolvers_reject_parent_traversal():
    layout = ReeLayout.for_ree("/r", "ree1")
    with pytest.raises(ValueError):
        layout.upstream_file("../../escape")


@pytest.mark.parametrize("bad", ["", "with/slash", "with\\backslash", ".hidden"])
def test_validate_upload_token_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        validate_upload_token(bad)


def test_validate_upload_token_accepts_normal():
    validate_upload_token("abc123")
    validate_upload_token("token-with-dashes_and_underscores")
