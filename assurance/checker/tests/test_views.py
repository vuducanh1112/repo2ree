"""Specification views: the system map and the diff between two specifications."""

from __future__ import annotations

from pathlib import Path

from test_check import SPEC
from test_spec import documents

from repo2ree_assurance_checker.views import diff_specs, render_diff_markdown, system_map


def test_the_system_map_places_entities_in_their_owners_and_processes() -> None:
    drawn = system_map(SPEC)
    assert "subgraph process_api[api process]" in drawn
    assert "subgraph component_core[core]" in drawn
    assert "boundary_dispatch{{dispatch}}" in drawn
    assert "component_supervisor === boundary_dispatch ==> component_workbench" in drawn
    assert "AuthorApiAction -. api-success-is-recorded .-> Attempt" in drawn
    assert "Attempt -. example-execution-was-dispatched .-> boundary_dispatch" in drawn


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
