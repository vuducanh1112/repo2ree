"""The gate page saying where this tree's assessment of the gated runs differs from the receipt."""

from __future__ import annotations

import json
from pathlib import Path

from repo2ree_repoview.overview.pages.gates import judged_now as shown
from repo2ree_repoview.overview.receipt import ReceiptTest, judged_now


def test_this_trees_verdicts_are_read_from_the_report_of_each_run(tmp_path: Path) -> None:
    assert judged_now(tmp_path / "none") is None
    (tmp_path / "e2e-system-1").mkdir()
    record = {
        "tests": [
            {"name": "a", "directory": "tests/a", "behaviour": "violated"},
            {"name": "b", "directory": "tests/b"},
        ]
    }
    (tmp_path / "e2e-system-1/run.json").write_text(json.dumps(record))
    assert judged_now(tmp_path) == {("e2e-system-1", "a"): "violated", ("e2e-system-1", "b"): "missing"}


def test_the_gate_page_says_where_this_trees_checker_judges_differently() -> None:
    certified = ReceiptTest(run="r", test="t", outcome="passed", behaviour="passed")
    assert '<span class="no">violated</span>' in shown(certified, {("r", "t"): "violated"})
    assert "agrees" in shown(certified, {("r", "t"): "passed"})
    assert "just assess-behaviour" in shown(certified, None)
