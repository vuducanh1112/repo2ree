"""Executable specification selects mutation boundaries and inspects real paths."""

import runpy
from pathlib import Path

import pytest

_MODULE = runpy.run_path(str(Path(__file__).resolve().parents[2] / "specifications/system/verify_ree_layout.py"))
Boundary = _MODULE["Boundary"]
verify = _MODULE["verify"]


def _event(**changes):
    return Boundary.model_validate(
        {
            "observation_id": "attempt-1",
            "event": "operation_finished",
            "status": "succeeded",
            "scope": "author",
            "mutates_ree": True,
            "root_expected": True,
            "writers_stopped": True,
            "capture_prepared": True,
            "locks_held": True,
            "history_published": True,
            "capture_format": "legacy",
            **changes,
        }
    )


@pytest.mark.parametrize("status", ["succeeded", "failed", "canceled"])
def test_mutations_check_layout_regardless_of_outcome(tmp_path, status):
    report = verify(tmp_path, _event(status=status))
    assert report["verdict"] == "violated"
    assert {item["path"] for item in report["violations"]} == {"ree.json", ".git"}


@pytest.mark.parametrize("changes", [{"mutates_ree": False}, {"root_expected": False}])
def test_non_applicable_boundaries_do_not_inspect_missing_root(tmp_path, changes):
    assert verify(tmp_path / "missing", _event(**changes))["verdict"] == "not_applicable"


@pytest.mark.parametrize("field", ["writers_stopped", "capture_prepared", "locks_held"])
def test_unready_boundaries_are_inconclusive(tmp_path, field):
    assert verify(tmp_path, _event(**{field: False}))["verdict"] == "inconclusive"


def test_initialization_and_conditional_capture_requirements(tmp_path):
    (tmp_path / "ree.json").write_text("{}")
    (tmp_path / ".git").mkdir()
    (tmp_path / "user-file").write_text("allowed")
    assert verify(tmp_path, _event(event="initialization_finished", mutates_ree=False))["verdict"] == "passed"
    report = verify(tmp_path, _event(capture_format="repository_v2"))
    assert {item["path"] for item in report["violations"]} == {
        "run.sh",
        "REPRODUCING.md",
        ".gitattributes",
        ".gitignore",
    }


def test_review_without_history_and_managed_symlink(tmp_path):
    (tmp_path / "review.json").write_text("{}")
    event = _event(scope="review", history_published=False, capture_format="none")
    assert verify(tmp_path, event)["verdict"] == "passed"
    (tmp_path / "overlay").symlink_to(tmp_path, target_is_directory=True)
    assert verify(tmp_path, event)["violations"] == [
        {"path": "overlay", "expected": "directory", "observed": "symlink"}
    ]


def test_root_symlink_is_rejected_without_inspecting_target(tmp_path):
    root = tmp_path / "alias"
    root.symlink_to(tmp_path, target_is_directory=True)
    assert verify(root, _event())["violations"] == [{"path": ".", "expected": "directory", "observed": "symlink"}]
