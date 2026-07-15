"""Reproducibility scorecard.

Pure analysis layer: condenses the REE's *persisted record* — author intent,
session state, and the run receipts — into a per-category evidence scorecard
plus a single ordinal reproducibility level (R0..R5).

Everything here must stay derivable from the sealed bundle's contents alone
(intent + session + published receipts): no run-registry state, no UI badges,
no filesystem probing. That is what makes a stamped level auditable — anyone
holding the bundle can recompute it.

The level ladder is cumulative (min/bottleneck rule): level n holds only when
the predicates for 1..n all hold. Four normative choices are baked in:

* Environment before execution: an activation pass only counts against the
  runtime digest it actually ran on, so ``Functional`` always means
  "functional in the captured environment".
* Archival sits on top: a sealed bundle whose experiments never ran caps
  below ``Executed`` — publishing does not upgrade the claim.
* Descriptive completeness (metadata, HBOM) is out of scope: it is
  documentation quality, not reproducibility evidence.
* Availability requires fixed identity: ``Available`` needs the SWHID, not
  just a fetchable origin.

Functions carry design-by-contract assertions (pre-/post-conditions) for the
invariants that the type system cannot express.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.receipts import (
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    GenerateSbomReceipt,
    RunExperimentReceipt,
    RunReceipt,
    latest_successful_receipts,
)

SCORECARD_SCHEMA_VERSION: Literal[1] = 1

# The authoring UI records an explicitly skipped runtime under this sentinel;
# it must not count as a declared runtime.
_RUNTIME_SKIPPED = "__skipped__"

CategoryKey = Literal["source", "runtime", "activation", "experiments", "results"]

# Fixed category order — the wire contract renders in this order.
_CATEGORY_KEYS: tuple[CategoryKey, ...] = (
    "source",
    "runtime",
    "activation",
    "experiments",
    "results",
)

# R0..R5. Index == level.
LEVEL_NAMES: tuple[str, ...] = (
    "Draft",
    "Available",
    "Captured",
    "Functional",
    "Executed",
    "Archived",
)


# ================================================
# Data models
# ================================================


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ScoreCardRung(_CamelModel):
    """One checkable fact inside a category.

    Rungs are ordered strongest-last but are *independent* checkmarks, not a
    forced prefix: e.g. results can be bundled at seal time while the source
    was never SWH-archived.  ``done``/``total`` carry the fraction for rungs
    aggregated over the experiment list (``None`` elsewhere).
    """

    key: str
    label: str
    reached: bool
    detail: str = ""
    done: int | None = None
    total: int | None = None


class ScoreCardCategory(_CamelModel):
    key: CategoryKey
    label: str
    rungs: list[ScoreCardRung]


class ReproducibilityScoreCard(_CamelModel):
    """The scorecard: five evidence categories + the ordinal level.

    ``level`` is the bottleneck aggregate (see module docstring); the code and
    name are derived from it so they can never drift.
    """

    schema_version: Literal[1] = SCORECARD_SCHEMA_VERSION
    level: int = Field(ge=0, le=5)
    sealed: bool
    categories: list[ScoreCardCategory]

    # mypy does not support decorators on properties (python/mypy#1362), so the
    # @computed_field lines need an explicit ignore.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def level_code(self) -> str:
        return f"R{self.level}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def level_name(self) -> str:
        return LEVEL_NAMES[self.level]


# ================================================
# Internals
# ================================================


def _digests_consistent(declared: str | None, produced: str | None) -> bool:
    """Whether a step's declared runtime digest matches the built runtime.

    Only a present-and-different pair is evidence of inconsistency; receipts
    predating digest capture (either side ``None``) stay acceptable.
    """
    if declared and produced:
        return declared == produced
    return True


def _short_digest(digest: str | None) -> str:
    if not digest:
        return ""
    # Digests are "algo:hex"; keep the tail readable.
    return digest.split(":", 1)[-1][:12]


class _Evidence:
    """The latest-successful receipts, narrowed to their operation types."""

    def __init__(self, intent: ReeIntent, receipts: list[RunReceipt]) -> None:
        latest = latest_successful_receipts(receipts)
        build = latest.get("build_runtime")
        sbom = latest.get("generate_sbom")
        crosscheck = latest.get("cross_check_sbom")
        activation = latest.get("activation_test")
        self.build = build if isinstance(build, BuildRuntimeReceipt) else None
        self.sbom = sbom if isinstance(sbom, GenerateSbomReceipt) else None
        self.crosscheck = crosscheck if isinstance(crosscheck, CrossCheckSbomReceipt) else None
        self.activation = activation if isinstance(activation, ActivationTestReceipt) else None
        self.experiments: dict[str, RunExperimentReceipt] = {}
        for experiment in intent.experiments:
            if not experiment.name:
                continue
            receipt = latest.get(f"experiment:{experiment.name}")
            if isinstance(receipt, RunExperimentReceipt):
                self.experiments[experiment.name] = receipt

    @property
    def runtime_digest(self) -> str | None:
        return self.build.produced_runtime_digest if self.build else None

    def runtime_built(self) -> bool:
        return self.build is not None

    def sbom_inventoried(self) -> bool:
        return (
            self.build is not None
            and self.sbom is not None
            and _digests_consistent(self.sbom.declared_runtime_digest, self.runtime_digest)
        )

    def sbom_cross_checked(self) -> bool:
        """The cross-check counts only against the SBOM currently in evidence:
        the digest chain (crosscheck → sbom → build) ties it to the runtime."""
        return (
            self.sbom_inventoried()
            and self.sbom is not None
            and self.crosscheck is not None
            and self.crosscheck.sbom_digest is not None
            and self.crosscheck.sbom_digest == self.sbom.sbom_digest
        )

    def activation_passed(self) -> bool:
        return (
            self.build is not None
            and self.activation is not None
            and _digests_consistent(self.activation.declared_runtime_digest, self.runtime_digest)
        )

    def experiment_validated(self, name: str, *, declares_outputs: bool) -> bool:
        """Validated = latest run succeeded against the built runtime and, when
        outputs are declared, their baseline digest was captured."""
        receipt = self.experiments.get(name)
        if receipt is None or self.build is None:
            return False
        if not _digests_consistent(receipt.declared_runtime_digest, self.runtime_digest):
            return False
        if declares_outputs and not receipt.produced_output_digest:
            return False
        return True

    def outputs_captured(self, name: str) -> bool:
        receipt = self.experiments.get(name)
        return receipt is not None and bool(receipt.produced_output_digest)


def _source_category(intent: ReeIntent, session: ReeSession) -> ScoreCardCategory:
    linked = bool(intent.origin_url or session.uploaded_archive)
    return ScoreCardCategory(
        key="source",
        label="Source",
        rungs=[
            ScoreCardRung(
                key="linked",
                label="Linked",
                reached=linked,
                detail=intent.origin_url or (session.uploaded_archive or ""),
            ),
            ScoreCardRung(key="acquired", label="Acquired", reached=session.source_available),
            ScoreCardRung(
                key="archived",
                label="SWH-archived",
                reached=bool(intent.swhid),
                detail=intent.swhid,
            ),
            ScoreCardRung(key="included", label="Included", reached=session.source_included),
        ],
    )


def _runtime_category(intent: ReeIntent, session: ReeSession, evidence: _Evidence) -> ScoreCardCategory:
    declared = bool(intent.runtime) and intent.runtime != _RUNTIME_SKIPPED
    return ScoreCardCategory(
        key="runtime",
        label="Runtime",
        rungs=[
            # A built runtime implies availability even if the intent field
            # lags — the rung must not read weaker than the evidence.
            ScoreCardRung(
                key="available",
                label="Available",
                reached=declared or evidence.runtime_built(),
            ),
            ScoreCardRung(
                key="built",
                label="Built",
                reached=evidence.runtime_built(),
                detail=_short_digest(evidence.runtime_digest),
            ),
            ScoreCardRung(
                key="inventoried",
                label="SBOM",
                reached=evidence.sbom_inventoried(),
                detail=_short_digest(evidence.sbom.sbom_digest) if evidence.sbom else "",
            ),
            # Non-gating evidence: the fraction of declared direct deps
            # observed in the runtime. Deliberately not part of the R-level —
            # dev/build-only deps legitimately never reach the runtime.
            ScoreCardRung(
                key="crossChecked",
                label="Cross-checked",
                reached=evidence.sbom_cross_checked(),
                done=evidence.crosscheck.observed_matched if evidence.crosscheck else None,
                total=evidence.crosscheck.declared_direct_total if evidence.crosscheck else None,
            ),
            ScoreCardRung(key="included", label="Included", reached=session.runtime_included),
        ],
    )


def _activation_category(evidence: _Evidence) -> ScoreCardCategory:
    return ScoreCardCategory(
        key="activation",
        label="Activation",
        rungs=[
            ScoreCardRung(
                key="passed",
                label="Passed",
                reached=evidence.activation_passed(),
            )
        ],
    )


def _experiments_category(intent: ReeIntent, evidence: _Evidence) -> ScoreCardCategory:
    named = [experiment for experiment in intent.experiments if experiment.name]
    validated = [
        experiment.name
        for experiment in named
        if evidence.experiment_validated(experiment.name, declares_outputs=bool(experiment.output_paths))
    ]
    return ScoreCardCategory(
        key="experiments",
        label="Experiments",
        rungs=[
            ScoreCardRung(
                key="validated",
                label="Validated",
                reached=bool(named) and len(validated) == len(named),
                done=len(validated),
                total=len(named),
            )
        ],
    )


def _results_category(intent: ReeIntent, session: ReeSession, evidence: _Evidence) -> ScoreCardCategory:
    with_outputs = [experiment for experiment in intent.experiments if experiment.name and experiment.output_paths]
    captured = [experiment.name for experiment in with_outputs if evidence.outputs_captured(experiment.name)]
    return ScoreCardCategory(
        key="results",
        label="Results",
        rungs=[
            ScoreCardRung(
                key="captured",
                label="Captured",
                reached=bool(with_outputs) and len(captured) == len(with_outputs),
                done=len(captured),
                total=len(with_outputs),
            ),
            ScoreCardRung(key="included", label="Included", reached=session.results_included),
        ],
    )


def _rung_reached(categories: list[ScoreCardCategory], category_key: CategoryKey, rung_key: str) -> bool:
    for category in categories:
        if category.key != category_key:
            continue
        for rung in category.rungs:
            if rung.key == rung_key:
                return rung.reached
    raise AssertionError(f"unknown rung: {category_key}/{rung_key}")


def _level(categories: list[ScoreCardCategory], session: ReeSession) -> int:
    """The cumulative ladder over the categories' rungs (module docstring)."""

    def reached(category_key: CategoryKey, rung_key: str) -> bool:
        return _rung_reached(categories, category_key, rung_key)

    predicates = (
        # R1 Available — the source is held and permanently identified.
        reached("source", "acquired") and reached("source", "archived"),
        # R2 Captured — the environment exists and is inventoried.
        reached("runtime", "built") and reached("runtime", "inventoried"),
        # R3 Functional — the captured environment demonstrably runs.
        reached("activation", "passed"),
        # R4 Executed — every declared experiment ran and captured its outputs.
        # (Deliberately not "Reproduced": a single baseline run proves nothing
        # was re-produced; digest-matching re-runs would be a higher claim.)
        reached("experiments", "validated"),
        # R5 Archived — sealed with source, runtime and results all bundled.
        session.is_sealed
        and reached("source", "included")
        and reached("runtime", "included")
        and reached("results", "included"),
    )
    level = 0
    for predicate in predicates:
        if not predicate:
            break
        level += 1
    return level


# ================================================
# Entry point
# ================================================


def build_scorecard(
    intent: ReeIntent,
    session: ReeSession,
    receipts: list[RunReceipt],
) -> ReproducibilityScoreCard:
    """Build the reproducibility scorecard from the REE's persisted record."""

    evidence = _Evidence(intent, receipts)
    categories = [
        _source_category(intent, session),
        _runtime_category(intent, session, evidence),
        _activation_category(evidence),
        _experiments_category(intent, evidence),
        _results_category(intent, session, evidence),
    ]

    if tuple(category.key for category in categories) != _CATEGORY_KEYS:
        raise AssertionError("scorecard categories must be exactly the five, in order")
    for category in categories:
        for rung in category.rungs:
            if (rung.done is None) != (rung.total is None):
                raise AssertionError("rung fraction must set done and total together")
            if rung.done is not None and rung.total is not None and not 0 <= rung.done <= rung.total:
                raise AssertionError("rung fraction must satisfy 0 <= done <= total")

    return ReproducibilityScoreCard(
        level=_level(categories, session),
        sealed=session.is_sealed,
        categories=categories,
    )
