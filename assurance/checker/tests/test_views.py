"""Specification views: the system map, the report, and the diff between two specifications."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_spec import documents
from test_system_assurance import GIT, SPEC, authoring_and_sealing, make_system

from repo2ree_assurance_checker.check import replay
from repo2ree_assurance_checker.html import render_html
from repo2ree_assurance_checker.sources import load_evidence
from repo2ree_assurance_checker.views import diff_specs, render_diff_markdown, system_map


@pytest.fixture(scope="module")
def sealed(tmp_path_factory: pytest.TempPathFactory) -> tuple[object, object]:
    monkeypatch = pytest.MonkeyPatch()
    tmp = tmp_path_factory.mktemp("sealed")
    try:
        system = make_system(tmp, monkeypatch)
        result = authoring_and_sealing(system)
        evidence = load_evidence([tmp / "journal"], [system.layout.root], str(GIT), [tmp / "stores"])
        return result, replay(SPEC, evidence)[0]
    finally:
        monkeypatch.undo()


def test_the_system_map_places_entities_in_their_owners_and_processes() -> None:
    drawn = system_map(SPEC)
    assert "subgraph process_api[api process]" in drawn
    assert "subgraph component_core[core]" in drawn
    assert "boundary_dispatch{{dispatch}}" in drawn
    assert "component_supervisor === boundary_dispatch ==> component_workbench" in drawn
    assert "AuthorApiAction -. api-success-is-recorded .-> Attempt" in drawn
    assert "Attempt -. example-execution-was-dispatched .-> boundary_dispatch" in drawn


def test_the_html_report_draws_every_view(sealed: tuple[object, object]) -> None:
    result, _ = sealed
    page = render_html(SPEC, result)  # type: ignore[arg-type]
    assert page.count('<pre class="mermaid">') == 1 + len(SPEC.entities)  # The map, and one chart per entity.
    assert "just trace-dossier" in page
    assert "<script" in page
    assert "violated</span> ·" not in page


def test_a_specification_change_is_drawn_as_a_diff(tmp_path: Path) -> None:
    docs = documents()
    action = docs.machine("AuthorApiAction")
    # The work finishing before the cancel took effect.
    action["transitions"] = [t for t in action["transitions"] if not (t["from"] == "canceling" and "failed" in t["to"])]
    docs.invariants["invariant"] = docs.invariants["invariant"][1:]
    old, new = documents().parse(), docs.parse()
    diff = diff_specs(old, new)
    action_diff = next(machine for machine in diff.machines if machine.entity == "AuthorApiAction")
    assert set(action_diff.removed_edges) == {("canceling", "succeeded"), ("canceling", "failed")}
    assert diff.removed_invariants == ("dispatch-success-is-captured",)
    rendered = render_diff_markdown(diff, old.digest, new.digest)
    assert "canceling --> succeeded: - removed" in rendered
    assert diff_specs(old, old).empty
