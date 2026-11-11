"""The REE page: its evidence graph, every part, what moved each, and what the spec allows but nothing took."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from repo2ree_repoview.overview import figures
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import SPEC_EXPORT, Operations, Spec, exported
from repo2ree_repoview.overview.pages.aggregate import page_aggregate
from repo2ree_repoview.overview.pages.coverage import page_coverage
from repo2ree_repoview.overview.pages.specification import page_specification
from repo2ree_repoview.overview.receipt import AggregateMoves, Evidence, Exercised
from repo2ree_repoview.overview.spec_diagrams import drawings, part_drawing


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


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return Bundle(tmp_path / "overview", "a" * 40)


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


REPORT = {
    "aggregates": [
        {
            "aggregate": "Ree",
            "instances": 2,
            "moves": [
                moves("receipt", "experiment_environment", "missing", "current", "build_experiment_environment"),
                moves("field", "definition.catalog.version", "unset", "set", "run_experiment", allowed=False),
            ],
            "findings": [{"verdict": "violated", "subject": "Ree r definition.catalog.version", "reason": "x"}],
        }
    ]
}


def test_each_part_is_drawn_with_the_operations_that_moved_it(tmp_path: Path) -> None:
    drawn = drawings(spec(), run_with(tmp_path, REPORT), {}, Evidence())
    assert "build_experiment_environment 3" in drawn[part_drawing("Ree", "experiment_environment")]
    assert "run_experiment 3 ✗" in drawn[part_drawing("Ree", "definition.catalog.version")]
    assert part_drawing("Ree", "definition.experiments[*]") == "spec/aggregates/Ree/definition.experiments.svg"


def test_the_page_shows_each_part_as_drawn_and_lists_what_nothing_took(
    tmp_path: Path, bundle: Bundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(figures, "DIAGRAMS", tmp_path / "diagrams")
    drawn = tmp_path / "diagrams" / part_drawing("Ree", "experiment_environment")
    drawn.parent.mkdir(parents=True)
    drawn.write_text('<?xml version="1.0"?>\n<svg viewBox="0 0 1 1"><g id="runtime-part"/></svg>\n')
    tally = AggregateMoves.over(run_with(tmp_path, REPORT), "Ree")
    page = page_aggregate(spec().aggregates["Ree"], tally, bundle).body
    assert '<svg viewBox="0 0 1 1"><g id="runtime-part"/></svg>' in page
    assert (bundle.root / "diagrams" / part_drawing("Ree", "experiment_environment")).is_file()
    # A part not drawn yet says how to draw it.
    assert "Missing: run <code>just generate-spec-diagrams</code>" in page
    assert "Ree r definition.catalog.version: x" in page
    # Never taken, and listed; what only whole-document loading allows is not, unless named outright.
    assert "missing → current by build_experiment_environment" not in page
    assert "stale → current by build_experiment_environment" in page
    assert "missing → stale by load_ree_bundle" not in page
    assert "draft → sealed by load_ree_bundle" in page


def test_reports_from_before_aggregates_say_so_instead_of_showing_nothing_moved(tmp_path: Path, bundle: Bundle) -> None:
    tally = AggregateMoves.over(run_with(tmp_path, {"rules": []}), "Ree")
    assert not tally.recorded
    assert "predate aggregate reporting" in page_aggregate(spec().aggregates["Ree"], tally, bundle).body


def test_entities_without_a_machine_are_listed_not_drawn_and_point_to_their_parts(
    tmp_path: Path, bundle: Bundle
) -> None:
    current = spec()
    exercised = Exercised.over(run_with(tmp_path, {"rules": []}))
    coverage = page_coverage(current, None, exercised, {}, {}, no_operations(), bundle).body
    for body in (coverage, page_specification(current, bundle).body):
        assert "<b>Receipt</b>" not in body
        assert '<a href="ree.html">REE</a>' in body


def test_the_count_leaves_out_bulk_operations_and_groups_follow_the_checkers_order(
    tmp_path: Path, bundle: Bundle
) -> None:
    ree = spec().aggregates["Ree"]
    allowed = sum(op not in m.bulk for m in ree.machines for edge in m.edges for op in edge.by)
    page = page_aggregate(ree, AggregateMoves.over(run_with(tmp_path, {"aggregates": []}), "Ree"), bundle).body
    assert f"of {allowed} allowed moves" in page
    sections = [chunk.split("</h3>", 1)[0] for chunk in page.split("<h3>")[1:]]
    assert sections == ["Evidence graph", "Parts"]
    groups = [chunk.split("</h4>", 1)[0] for chunk in page.split("<h4>")[1:]]
    assert groups == list(dict.fromkeys(machine.group for machine in ree.machines))
