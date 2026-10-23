"""A sealed REE's provenance: each step's evidence at seal, the operation that produced it, and its chain."""

from __future__ import annotations

from traceview_scenario import SPEC, build_spans, recorded, trace_of

from repo2ree_assurance_traceview.provenance import build_provenance, render_text


def test_the_sealed_scenario_conforms() -> None:
    assert trace_of(recorded(sealed=True)).verdict == "passed"


def test_standings_show_evidence_going_stale_and_current_again() -> None:
    standings = trace_of(recorded(sealed=True)).standings
    runtime = [column.states.get("runtime") for column in standings]
    assert runtime == ["missing", "current", "current", "current", "stale", "current", "current", "current"]
    assert [column.label for column in standings][-1] == "seal_ree"
    assert [column.sealed for column in standings][-2:] == [False, True]


def test_an_unsealed_recording_has_no_provenance() -> None:
    assert build_provenance(trace_of(recorded())) is None


def test_each_step_is_traced_to_the_operation_that_last_produced_it() -> None:
    provenance = build_provenance(trace_of(recorded(sealed=True)))
    assert provenance is not None
    origins = {origin.step: origin for origin in provenance.steps}
    assert provenance.standing == {"runtime": "current", "sbom": "current", "test_activation": "missing"}
    # Runtime went stale and was rebuilt: its receipt is the first build's, refreshed in place.
    assert origins["runtime"].produced_by == "build_runtime"
    assert origins["runtime"].later == ("current → stale by authoring", "stale → current by build_runtime")
    assert origins["test_activation"].change is None
    assert origins["test_activation"].history == ("undeclared", "missing")
    assert provenance.after_seal == 0


def test_every_link_carries_the_rules_its_own_events_triggered() -> None:
    provenance = build_provenance(trace_of(recorded(sealed=True), build_spans()))
    assert provenance is not None
    runtime = next(origin for origin in provenance.steps if origin.step == "runtime")
    # Which rules a subject triggers is the specification's to say; each link holds only its own subject's.
    assert {rule.rule for rule in runtime.rules} <= triggered_by("Receipt")
    links = {link.label.split(" ", 1)[0]: link for link in runtime.chain}
    assert {rule.rule for rule in links["attempt"].rules} <= triggered_by("Attempt")
    assert {rule.rule for rule in links["dispatch"].rules} == {"dispatch-success-is-captured"}
    assert "api-success-is-recorded" in {rule.rule for rule in links["action"].rules}
    assert {rule.rule for rule in links["action"].rules} <= triggered_by("AuthorApiAction")
    assert runtime.chain[-1].label == "POST /rees/{id}/build-runtime → 202 at +10 s"
    assert {rule.rule for rule in provenance.seal_rules} >= {"sealed-without-stale-evidence"}


def triggered_by(subject: str) -> set[str]:
    return {
        invariant.id
        for invariant in SPEC.invariants
        if getattr(invariant.when, "entity", None) == subject or getattr(invariant.when, "boundary", None) == subject
    }


def test_provenance_renders_as_a_tree() -> None:
    provenance = build_provenance(trace_of(recorded(sealed=True)))
    assert provenance is not None
    text = render_text(provenance)
    assert "SEALED @c8000000" in text
    assert "└─ test_activation" in text
    assert "never produced: undeclared → missing" in text
    tree = text.split("\n[git]")[0]  # Above the legend.
    assert "✗" not in tree
