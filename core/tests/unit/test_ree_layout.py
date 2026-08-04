import dataclasses
from pathlib import Path

import pytest

from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.persistence.layout import (
    BUNDLE_ACQUIRE_ENTRY_PATH,
    BUNDLE_ARTIFACTS_PREFIX,
    BUNDLE_MATERIALIZE_ENTRY_PATH,
    BUNDLE_OVERLAY_PREFIX,
    BUNDLE_REE_MANIFEST_ENTRY_PATH,
    BUNDLE_REPRODUCER_README_ENTRY_PATH,
    BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH,
    BUNDLE_RESULTS_PREFIX,
    BUNDLE_ROOT_PREFIX,
    BUNDLE_SNAPSHOT_ENTRY_PATH,
    ReeLayout,
    validate_upload_token,
)


def test_for_ree_composes_root_from_storage_root_and_id():
    layout = ReeLayout.for_ree("/var/lib/repo2ree", "abc123")
    assert layout.root == Path("/var/lib/repo2ree/abc123")


def test_for_ree_accepts_path_storage_root():
    layout = ReeLayout.for_ree(Path("/var/lib/repo2ree"), "abc123")
    assert layout.root == Path("/var/lib/repo2ree/abc123")


def test_top_level_paths_are_derived_from_root():
    layout = ReeLayout.for_ree("/r", "ree1")
    assert layout.manifest == Path("/r/ree1/ree.json")
    assert layout.snapshot_archive == Path("/r/ree1/snapshot.tar.gz")
    assert layout.upload_staging == Path("/r/ree1/upload-staging")
    assert layout.upstream == Path("/r/ree1/upstream")
    assert layout.overlay == Path("/r/ree1/overlay")
    assert layout.artifacts == Path("/r/ree1/artifacts")
    assert layout.workspace == Path("/r/ree1/workspace")


def test_relative_resolvers_join_under_their_subtree():
    layout = ReeLayout.for_ree("/r", "ree1")
    assert layout.overlay_file("Dockerfile") == Path("/r/ree1/overlay/Dockerfile")
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
        layout.workspace_file("../../escape")


@pytest.mark.parametrize("bad", ["", "with/slash", "with\\backslash", ".hidden"])
def test_validate_upload_token_rejects_unsafe(bad):
    with pytest.raises(ValueError):
        validate_upload_token(bad)


def test_validate_upload_token_accepts_normal():
    validate_upload_token("abc123")
    validate_upload_token("token-with-dashes_and_underscores")


def test_the_published_bundle_layout_is_a_format_promise():
    """These strings are in every bundle ever published.

    They are derived from the dirnames above them so the bundle cannot drift
    from the tree it mirrors — which also means a rename there silently changes
    what repo2ree publishes, and a reader holding last year's bundle resolves
    these literally. Pinned here so that change has to be made on purpose.
    """
    assert BUNDLE_ROOT_PREFIX == "ree/"
    assert BUNDLE_REE_MANIFEST_ENTRY_PATH == "ree/ree.json"
    assert BUNDLE_SNAPSHOT_ENTRY_PATH == "ree/snapshot.tar.gz"
    assert BUNDLE_OVERLAY_PREFIX == "ree/overlay/"
    assert BUNDLE_ARTIFACTS_PREFIX == "ree/artifacts/"
    assert BUNDLE_RESULTS_PREFIX == "ree/results/"
    assert BUNDLE_ACQUIRE_ENTRY_PATH == "ree/acquire_source.sh"
    assert BUNDLE_MATERIALIZE_ENTRY_PATH == "ree/materialize_workspace.sh"
    assert BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH == "run.sh"
    assert BUNDLE_REPRODUCER_README_ENTRY_PATH == "REPRODUCING.md"


def test_an_ree_root_and_a_review_root_are_the_same_tree():
    """What lets the shared acquire and materialize scripts run in both."""
    layout = ReeLayout.for_ree("/r", "ree1")
    review = layout.review("attempt-1")

    def tree_paths(root_layout):
        return [
            path.relative_to(root_layout.root)
            for path in (
                root_layout.acquire_script,
                root_layout.materialize_script,
                root_layout.snapshot_archive,
                root_layout.upstream,
                root_layout.overlay,
                root_layout.workspace,
                root_layout.artifacts,
                root_layout.sbom,
            )
        ]

    assert tree_paths(layout) == tree_paths(review)
    assert review.root == Path("/r/ree1/reviews/attempt-1")
    # An attempt keeps its own evidence where an REE keeps its record.
    assert review.sbom == Path("/r/ree1/reviews/attempt-1/artifacts/sbom.json")
    assert review.metadata == Path("/r/ree1/reviews/attempt-1/review.json")
