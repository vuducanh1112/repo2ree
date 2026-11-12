"""The layout joins the REE tree's names: every path it makes is an entry the tree names, captured as the tree says."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from repo2ree_core.persistence.capture_policy import capture_plan
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_ree.layout import REE_TREE

ROOT = Path("/r/ree1")


def made_by(layout: ReeLayout) -> dict[str, Path]:
    """Every path the layout spells: its properties, and each resolver with a sample key."""
    paths = {
        name: getattr(layout, name)
        for name in dir(type(layout))
        if isinstance(getattr(type(layout), name), property) and isinstance(getattr(layout, name), Path)
    }
    paths |= {
        "run_log": layout.run_log("run-1"),
        "run_cancel_marker": layout.run_cancel_marker("run-1"),
        "results_dir": layout.results_dir("train"),
        "upload_staging_file": layout.upload_staging_file("token"),
        "overlay_file": layout.overlay_file("ree-scripts/experiments/train.sh"),
    }
    if isinstance(layout, ReviewLayout):
        paths |= {
            "run_receipt": layout.run_receipt("run-1"),
            "operation_receipt": layout.operation_receipt("build_experiment_environment"),
            "comparison": layout.comparison("build_experiment_environment"),
            "experiment_receipt": layout.experiment_receipt("train"),
            "experiment_comparison": layout.experiment_comparison("train"),
        }
    paths.pop("root", None)
    return paths


@pytest.mark.parametrize(
    "layout", [ReeLayout(root=ROOT), ReeLayout(root=ROOT).review("attempt-1")], ids=["ree", "review"]
)
def test_every_path_the_layout_makes_is_an_entry_of_the_tree(layout: ReeLayout) -> None:
    for name, path in made_by(layout).items():
        relative = PurePosixPath(path.relative_to(ROOT).as_posix())
        entry = REE_TREE.find(relative)
        assert entry.names(relative.name), f"{name}: {relative} falls in {entry.name}, which does not name it"


def test_what_a_capture_commits_the_tree_marks_as_committed(tmp_path: Path) -> None:
    layout = ReeLayout(root=tmp_path)
    for path in made_by(layout).values():
        if path.suffix and path.parent.name != "upload-staging":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")
    for name in (".gitattributes", ".gitignore", "run.sh", "REPRODUCING.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    plan = capture_plan(layout, None)
    assert plan.entries
    for entry in plan.entries:
        assert REE_TREE.find(entry.path).capture == entry.storage, entry.path
