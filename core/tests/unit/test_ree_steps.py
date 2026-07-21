from __future__ import annotations

from repo2ree_core.domain.hbom import HBOM, CPUDefinition
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.experiment import Experiment
from repo2ree_core.ree_steps import (
    REE_STEPS,
    ReeStepState,
    build_ree_step_states,
    ree_step_catalog,
)


def _status(states: list[ReeStepState], key: str) -> tuple[str, list[str]]:
    step = next(state for state in states if state.key == key)
    return step.status, step.blocked_by


# ================================================
# Static structure
# ================================================


def test_catalog_is_acyclic_and_references_known_steps() -> None:
    keys = {step.key for step in REE_STEPS}
    seen: set[str] = set()
    for step in REE_STEPS:  # REE_STEPS is in dependency-respecting order
        for requirement in step.requires:
            assert requirement in keys, f"{step.key} requires unknown step {requirement}"
            assert requirement in seen, f"{step.key} requires later/unordered step {requirement}"
        seen.add(step.key)


def test_catalog_orders_are_unique_and_sequential() -> None:
    orders = [step.order for step in ree_step_catalog()]
    assert orders == list(range(1, len(orders) + 1))


# ================================================
# Status overlay
# ================================================


def test_empty_ree_gates_everything_on_authoring() -> None:
    states = build_ree_step_states(
        ReeIntent(),
        ReeSession(),
        completed_run_steps=set(),
        evaluate_report_present=False,
    )
    # Steps with no prerequisites are immediately actionable...
    assert _status(states, "source") == ("ready", [])
    assert _status(states, "metadata") == ("ready", [])
    assert _status(states, "seal") == ("ready", [])
    # ...while run steps are blocked by their missing prerequisites.
    assert _status(states, "build") == ("blocked", ["source"])
    assert _status(states, "sbom") == ("blocked", ["build"])
    assert _status(states, "crosscheck") == ("blocked", ["sbom", "evaluate"])


def test_authoring_fields_mark_their_steps_done() -> None:
    intent = ReeIntent(
        name="demo",
        hardware_description=HBOM(cpus={"Intel Core i9": CPUDefinition(vendor="Intel")}),
    )
    session = ReeSession(source_available=True)
    states = build_ree_step_states(
        intent,
        session,
        completed_run_steps=set(),
        evaluate_report_present=True,
    )
    assert _status(states, "source") == ("done", [])
    assert _status(states, "metadata") == ("done", [])
    assert _status(states, "hbom") == ("done", [])
    assert _status(states, "evaluate") == ("done", [])
    # Source is done, so build is now reachable.
    assert _status(states, "build") == ("ready", [])


def test_recorded_build_unblocks_sbom_and_activation() -> None:
    session = ReeSession(source_available=True)
    states = build_ree_step_states(
        ReeIntent(name="demo"),
        session,
        completed_run_steps={"build_runtime"},
        evaluate_report_present=False,
    )
    assert _status(states, "build") == ("done", [])
    assert _status(states, "sbom") == ("ready", [])
    assert _status(states, "activation") == ("ready", [])
    # Cross-check still waits on both the SBOM and the evaluate report.
    assert _status(states, "crosscheck") == ("blocked", ["sbom", "evaluate"])


def test_completion_is_run_presence_not_freshness() -> None:
    # A recorded build stays done regardless of any later staleness — completion
    # is "a run happened", the same signal the frontend badges use. (Staleness is
    # the consistency report's concern, not this overlay's.)
    session = ReeSession(source_available=True)
    states = build_ree_step_states(
        ReeIntent(name="demo"),
        session,
        completed_run_steps={"build_runtime"},
        evaluate_report_present=False,
    )
    assert _status(states, "build") == ("done", [])


def test_crosscheck_needs_its_own_run_after_sbom_and_evaluate() -> None:
    session = ReeSession(source_available=True)
    # SBOM run and evaluate report present, but cross-check not yet run: ready.
    ready = build_ree_step_states(
        ReeIntent(name="demo"),
        session,
        completed_run_steps={"build_runtime", "generate_sbom"},
        evaluate_report_present=True,
    )
    assert _status(ready, "crosscheck") == ("ready", [])

    done = build_ree_step_states(
        ReeIntent(name="demo"),
        session,
        completed_run_steps={"build_runtime", "generate_sbom", "cross_check_sbom"},
        evaluate_report_present=True,
    )
    assert _status(done, "crosscheck") == ("done", [])


def test_experiments_done_only_when_all_named_have_run() -> None:
    intent = ReeIntent(
        name="demo",
        experiments=[Experiment(name="one"), Experiment(name="two")],
    )
    session = ReeSession(source_available=True)
    partial = build_ree_step_states(
        intent,
        session,
        completed_run_steps={"build_runtime", "experiment:one"},
        evaluate_report_present=False,
    )
    assert _status(partial, "experiments") == ("ready", [])

    complete = build_ree_step_states(
        intent,
        session,
        completed_run_steps={"build_runtime", "experiment:one", "experiment:two"},
        evaluate_report_present=False,
    )
    assert _status(complete, "experiments") == ("done", [])
