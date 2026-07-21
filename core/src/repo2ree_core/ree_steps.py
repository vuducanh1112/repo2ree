"""The REE authoring steps: the ordered checklist and its prerequisite graph.

This is the operational counterpart of the reproducibility scorecard. The
scorecard answers *how reproducible is this* (an assessment, on the R0-R5
ladder); the steps answer *what is there to do, in what order, and what can run
now* (navigation). They are deliberately separate concerns over the same
persisted record: a step keyed by the operation an automation client calls, not
by a scored evidence rung.

The step list and its ``requires`` edges are the single declared source of the
authoring graph — the same steps the frontend renders as its process ring
(``REE_STEPS`` there), lifted out of the UI so a machine client (or a second UI)
reads the identical structure instead of re-deriving it. ``build_ree_step_states``
overlays per-REE state onto that static list: each step is ``done`` (a
successful run, or the authoring input it needs, is recorded), ``ready`` (all
prerequisites done, actionable now), or ``blocked`` (named prerequisites still
missing).

Status is derived, never stored, from the persisted record on each fetch.
Completion matches the frontend badges and the scorecard — *a run happened* —
not freshness: whether a completed step has since gone stale is a separate axis,
left to the ``consistency`` report, so a client can show "done, but stale"
rather than have the step silently revert.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession

# ================================================
# Static structure — the authoring step graph
# ================================================


class ReeStep(BaseModel):
    """One node of the authoring checklist: its position and prerequisites.

    Purely structural and deployment-static — the same for every REE. The
    concrete calls that advance a step (operationIds) are an HTTP concern and
    are joined on by the API layer, not carried here.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    order: int
    label: str
    requires: list[str] = Field(default_factory=list)


# The authoring steps, in operator order. ``requires`` names the steps whose
# evidence must exist before this one can run — the hard edges the run handlers
# enforce (a build before its SBOM/activation; both an SBOM and an evaluate
# report before the cross-check). Steps without a hard edge (source, metadata,
# hbom, seal) carry none: they are gated by authoring, not by a prior run.
REE_STEPS: tuple[ReeStep, ...] = (
    ReeStep(key="source", order=1, label="Source Acquisition"),
    ReeStep(key="metadata", order=2, label="Provide Metadata"),
    ReeStep(key="hbom", order=3, label="Hardware BOM"),
    ReeStep(key="evaluate", order=4, label="Reproducibility Readiness", requires=["source"]),
    ReeStep(key="build", order=5, label="Build Runtime", requires=["source"]),
    ReeStep(key="sbom", order=6, label="Generate SBOM", requires=["build"]),
    ReeStep(key="crosscheck", order=7, label="Cross-check SBOM", requires=["sbom", "evaluate"]),
    ReeStep(key="activation", order=8, label="Test Activation", requires=["build"]),
    ReeStep(key="experiments", order=9, label="Experiments", requires=["build"]),
    ReeStep(key="seal", order=10, label="Seal", requires=[]),
)


def ree_step_catalog() -> list[ReeStep]:
    """The static step catalog: the graph a client renders or plans against."""
    return list(REE_STEPS)


# ================================================
# Per-REE status — the overlay
# ================================================

StepStatus = Literal["done", "ready", "blocked"]


class ReeStepState(BaseModel):
    """The live state of one authoring step for a specific REE."""

    model_config = ConfigDict(extra="forbid")

    key: str
    status: StepStatus
    blocked_by: list[str] = Field(default_factory=list)


def _hbom_has_components(hbom: HBOM) -> bool:
    return any((hbom.cpus, hbom.gpus, hbom.memory, hbom.storage, hbom.network))


def build_ree_step_states(
    intent: ReeIntent,
    session: ReeSession,
    *,
    completed_run_steps: set[str],
    evaluate_report_present: bool,
) -> list[ReeStepState]:
    """Overlay per-REE state onto the static step list.

    Pure over its inputs — no filesystem — so it is unit-testable without a
    workbench. The caller (which has the layout) supplies the two evidence
    signals: the receipt-step keys with a recorded successful run
    (``latest_successful_receipts``), and whether the evaluate report artifact
    exists (evaluate records no receipt).

    A run-backed step is ``done`` once it has a recorded successful run — the
    same completion the frontend badges and the scorecard use, not freshness. A
    later edit that makes that run *stale* does not un-complete the step here;
    staleness is a separate axis, surfaced by the ``consistency`` report, so a
    client can show "done, but stale" rather than silently reverting the step.
    """
    named_experiments = [experiment.name for experiment in intent.experiments if experiment.name]

    def ran(step_key: str) -> bool:
        return step_key in completed_run_steps

    done: dict[str, bool] = {
        "source": session.source_available,
        "metadata": bool(intent.name.strip()),
        "hbom": _hbom_has_components(intent.hardware_description),
        "evaluate": evaluate_report_present,
        "build": ran("build_runtime"),
        "sbom": ran("generate_sbom"),
        "crosscheck": ran("cross_check_sbom"),
        "activation": ran("activation_test"),
        "experiments": bool(named_experiments) and all(ran(f"experiment:{name}") for name in named_experiments),
        "seal": session.is_sealed,
    }

    states: list[ReeStepState] = []
    for step in REE_STEPS:
        if done[step.key]:
            states.append(ReeStepState(key=step.key, status="done"))
            continue
        missing = [requirement for requirement in step.requires if not done[requirement]]
        states.append(
            ReeStepState(
                key=step.key,
                status="blocked" if missing else "ready",
                blocked_by=missing,
            )
        )
    return states
