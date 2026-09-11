"""State selection excludes bookkeeping and preserves declared evidence."""

import json

from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import INITIAL_REF, SELECTION_VERSION, open_history
from repo2ree_core.persistence.layout import ReeLayout


def test_layout_selection_and_declared_root_artifact(tmp_path):
    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="test")
    store = ReeDirectory(layout)
    ree = store.read_ree()
    assert ree.subject.definition.build_runtime is not None
    build = ree.subject.definition.build_runtime.model_copy(update={"runtime_path": "custom-runtime.tar"})
    definition = ree.subject.definition.model_copy(update={"build_runtime": build})
    store.write_ree(ree.model_copy(update={"subject": ree.subject.model_copy(update={"definition": definition})}))
    (layout.root / "custom-runtime.tar").write_bytes(b"runtime")
    (layout.root / "unknown").write_bytes(b"ignored")
    for tree in layout.history_trees:
        tree.mkdir(exist_ok=True)
        (tree / "arbitrary.tmp").write_bytes(b"state")
    layout.materialize_marker.write_text("{}")
    with open_history(layout) as history:
        commit = history.capture(operation="test")
        paths = history._git("ls-tree", "-r", "--name-only", commit).stdout.decode().splitlines()
    assert "custom-runtime.tar" in paths
    assert "unknown" not in paths
    assert ".workspace.materialized.json" in paths
    for tree in layout.history_trees:
        assert f"{tree.name}/arbitrary.tmp" in paths


def test_review_receipts_are_state_but_logs_are_not(tmp_path):
    layout = ReeLayout(root=tmp_path / "ree").review("attempt")
    layout.runs.mkdir(parents=True)
    layout.run_receipt("run").write_text("{}")
    layout.run_log("run").write_text("log")
    layout.metadata.write_text("{}")
    with open_history(layout) as history:
        commit = history.capture(operation="review")
        paths = history._git("ls-tree", "-r", "--name-only", commit).stdout.decode().splitlines()
    assert paths == ["review.json", "runs/run.receipt.json"]


def test_legacy_history_migrates_once_and_preserves_initial_ref(tmp_path):
    layout = ReeLayout(root=tmp_path / "ree")
    initial = initialize_ree(layout, name="test").snapshot_id
    with open_history(layout) as history:
        # An old whole-tree commit has no selection-version metadata.
        (layout.root / "legacy-log").write_text("log")
        history._git("add", "--", "legacy-log")
        tree = history._git("write-tree").stdout.decode().strip()
        legacy = history._git("commit-tree", tree, "-p", initial, data=b"old capture\n").stdout.decode().strip()
        history._git("update-ref", "refs/heads/ree-history", legacy)
        migrated = history.capture(operation="observe_existing_ree", reuse_unchanged=True)
        assert history._git("show", "-s", "--format=%s", migrated).stdout.strip() == b"migrate_history_selection"
        assert b"legacy-log" not in history._git("ls-tree", "-r", "--name-only", migrated).stdout
        assert history.capture(operation="observe_existing_ree", reuse_unchanged=True) == migrated
        metadata = json.loads(history._git("show", "-s", "--format=%b", migrated).stdout)
        assert metadata["selection_version"] == SELECTION_VERSION
        assert history._git("rev-parse", INITIAL_REF).stdout.decode().strip() == initial


def test_only_owned_temporary_files_are_excluded(tmp_path):
    from repo2ree_core.persistence.files import staging_path

    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="test")
    staged = staging_path(layout.sbom)
    staged.write_text("partial sbom")
    user_file = staging_path(layout.overlay_file("user.txt"))
    user_file.write_text("authored bytes")
    with open_history(layout) as history:
        commit = history.capture(operation="test")
        paths = history._git("ls-tree", "-r", "--name-only", commit).stdout.decode().splitlines()
    assert staged.relative_to(layout.root).as_posix() not in paths
    assert user_file.relative_to(layout.root).as_posix() in paths


def test_review_history_is_not_exposed_in_file_views(tmp_path):
    import pytest

    from repo2ree_core.operations.read_models.files import list_ree_files, list_workspace_files, read_ree_file_bytes

    layout = ReeLayout(root=tmp_path / "ree")
    initialize_ree(layout, name="test")
    review = layout.review("attempt")
    with open_history(review) as history:
        history.capture(operation="review")
    (layout.workspace / "review-config").symlink_to(review.git_dir / "config")
    assert not any(".git/" in entry.path for entry in list_ree_files(layout))
    assert not any(entry.path == "review-config" for entry in list_workspace_files(layout))
    for path in ("reviews/attempt/.git/config", "workspace/review-config"):
        with pytest.raises(ValueError, match="Invalid REE file path"):
            read_ree_file_bytes(layout, path)
