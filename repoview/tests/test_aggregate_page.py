"""The Ree machine page: every part of the REE, what moved it, and what the specification allows but nothing took."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from repo2ree_repoview.overview.exports import SPEC_EXPORT, Operations, Spec, exported
from repo2ree_repoview.overview.pages.aggregate import page_aggregate
from repo2ree_repoview.overview.pages.coverage import page_coverage
from repo2ree_repoview.overview.pages.specification import page_specification
from repo2ree_repoview.overview.receipt import AggregateMoves, Evidence, Exercised


def spec() -> Spec:
    return Spec.model_validate_json(exported(SPEC_EXPORT))


def moves(
    kind: str, machine: str, source: str, target: str, operation: str, *, allowed: bool = True
) -> dict[str, object]:
    return {
        "kind": kind,
        "machine": machine,
        "source": source,
        "target": target,
        "operation": operation,
        "count": 3,
        "allowed": allowed,
    }


def no_operations() -> Operations:
    return Operations.model_validate({"format": "repo2ree-operations/1", "lanes": [], "operations": []})


def run_with(tmp_path: Path, report: Mapping[str, object]) -> Evidence:
    verification = tmp_path / "run" / "tests" / "one" / "verification"
    verification.mkdir(parents=True)
    (verification / "assurance.json").write_text(json.dumps(report))
    return Evidence(runs=(tmp_path / "run",))


def test_the_export_spells_out_every_part_of_the_ree() -> None:
    ree = spec().aggregates["Ree"]
    kinds = [machine.kind for machine in ree.machines]
    assert kinds[0] == "lifecycle"
    assert {machine.name for machine in ree.machines if machine.kind == "receipt"} == set(ree.receipts)
    assert {"definition.name", "definition.experiments[*]"} <= {m.name for m in ree.machines if m.kind == "field"}


def test_the_page_counts_what_moved_each_part_and_lists_what_nothing_took(tmp_path: Path) -> None:
    report = {
        "aggregates": [
            {
                "aggregate": "Ree",
                "instances": 2,
                "moves": [
                    moves("receipt", "runtime", "missing", "current", "build_runtime"),
                    moves("field", "definition.catalog.version", "unset", "set", "run_experiment", allowed=False),
                ],
                "findings": [{"verdict": "violated", "subject": "Ree r definition.catalog.version", "reason": "x"}],
            }
        ]
    }
    tally = AggregateMoves.over(run_with(tmp_path, report), "Ree")
    page = page_aggregate(spec().aggregates["Ree"], tally).body
    assert "build_runtime 3" in page
    assert "run_experiment 3 ✗" in page
    assert "Ree r definition.catalog.version: x" in page
    # Never taken, and listed; what only whole-document loading allows is not, unless named outright.
    assert "missing → current by build_runtime" not in page
    assert "stale → current by build_runtime" in page
    assert "missing → stale by load_ree_bundle" not in page
    assert "draft → sealed by load_ree_bundle" in page


def test_reports_from_before_aggregates_say_so_instead_of_showing_nothing_moved(tmp_path: Path) -> None:
    tally = AggregateMoves.over(run_with(tmp_path, {"rules": []}), "Ree")
    assert not tally.recorded
    assert "predate aggregate reporting" in page_aggregate(spec().aggregates["Ree"], tally).body


def test_entities_without_a_machine_are_listed_not_drawn_and_point_to_their_parts(tmp_path: Path) -> None:
    current = spec()
    exercised = Exercised.over(run_with(tmp_path, {"rules": []}))
    coverage = page_coverage(current, None, exercised, {}, {}, no_operations()).body
    for body in (coverage, page_specification(current).body):
        assert "<b>Receipt</b>" not in body
        assert '<a href="ree-machine.html">Ree machine</a>' in body
        assert "<b>Allocation</b>" in body


def test_the_count_leaves_out_bulk_operations_and_groups_follow_the_checkers_order(tmp_path: Path) -> None:
    ree = spec().aggregates["Ree"]
    allowed = sum(op not in m.bulk for m in ree.machines for edge in m.edges for op in edge.by)
    page = page_aggregate(ree, AggregateMoves.over(run_with(tmp_path, {"aggregates": []}), "Ree")).body
    assert f"of {allowed} allowed moves" in page
    headings = [chunk.split("</h3>", 1)[0] for chunk in page.split("<h3>")[1:]]
    assert headings == list(dict.fromkeys(machine.group for machine in ree.machines))
