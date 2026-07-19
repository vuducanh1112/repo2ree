from __future__ import annotations

import json

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.experiment import Experiment
from repo2ree_core.receipts import (
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    GenerateSbomReceipt,
    RunExperimentReceipt,
    RunReceipt,
)
from repo2ree_core.reproducibility_scorecard import (
    LEVEL_NAMES,
    ReproducibilityScoreCard,
    ScoreCardRung,
    build_scorecard,
)

_RUNTIME_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64
_OUTPUT_DIGEST = "sha256:" + "c" * 64


def _build_receipt(*, digest: str | None = _RUNTIME_DIGEST) -> BuildRuntimeReceipt:
    return BuildRuntimeReceipt(
        run_id="build-1",
        recorded_at="2026-01-01T00:00:00Z",
        status="succeeded",
        produced_runtime_digest=digest,
    )


def _sbom_receipt(*, declared: str | None = _RUNTIME_DIGEST) -> GenerateSbomReceipt:
    return GenerateSbomReceipt(
        run_id="sbom-1",
        recorded_at="2026-01-01T01:00:00Z",
        status="succeeded",
        declared_runtime_digest=declared,
        sbom_digest="sha256:" + "d" * 64,
    )


_SBOM_DIGEST = "sha256:" + "d" * 64


def _crosscheck_receipt(*, sbom_digest: str | None = _SBOM_DIGEST) -> CrossCheckSbomReceipt:
    return CrossCheckSbomReceipt(
        run_id="crosscheck-1",
        recorded_at="2026-01-01T01:30:00Z",
        status="succeeded",
        sbom_digest=sbom_digest,
        declared_direct_total=4,
        observed_matched=3,
    )


def _activation_receipt(*, declared: str | None = _RUNTIME_DIGEST) -> ActivationTestReceipt:
    return ActivationTestReceipt(
        run_id="act-1",
        recorded_at="2026-01-01T02:00:00Z",
        status="succeeded",
        declared_runtime_digest=declared,
    )


def _experiment_receipt(
    name: str,
    *,
    declared: str | None = _RUNTIME_DIGEST,
    output_digest: str | None = _OUTPUT_DIGEST,
    status: str = "succeeded",
) -> RunExperimentReceipt:
    return RunExperimentReceipt(
        run_id=f"exp-{name}",
        recorded_at="2026-01-01T03:00:00Z",
        status=status,  # type: ignore[arg-type]
        experiment_name=name,
        declared_runtime_digest=declared,
        produced_output_digest=output_digest,
    )


def _intent(*, experiments: list[Experiment] | None = None) -> ReeIntent:
    return ReeIntent(
        name="demo",
        origin_url="https://example.org/repo.git",
        swhid="swh:1:snp:" + "0" * 40,
        runtime="ree/runtime.tar",
        experiments=experiments if experiments is not None else [Experiment(name="fig1", output_paths=["out.csv"])],
    )


def _session(**overrides: object) -> ReeSession:
    base = ReeSession(source_available=True)
    return base.model_copy(update=overrides)


def _full_receipts() -> list[RunReceipt]:
    return [
        _build_receipt(),
        _sbom_receipt(),
        _activation_receipt(),
        _experiment_receipt("fig1"),
    ]


def _sealed_session() -> ReeSession:
    return _session(
        sealed_at="2026-01-02T00:00:00Z",
        seal_hash="sha256:" + "e" * 64,
        source_included=True,
        runtime_included=True,
        results_included=True,
    )


def _rung(card: ReproducibilityScoreCard, category_key: str, rung_key: str) -> ScoreCardRung:
    for category in card.categories:
        if category.key == category_key:
            for rung in category.rungs:
                if rung.key == rung_key:
                    return rung
    raise AssertionError(f"missing rung {category_key}/{rung_key}")


class TestLevelLadder:
    def test_empty_record_is_draft(self) -> None:
        card = build_scorecard(ReeIntent(), ReeSession(), [])
        assert card.level == 0
        assert card.level_code == "R0"
        assert card.level_name == "Draft"
        assert not card.sealed

    def test_acquired_and_archived_source_is_available(self) -> None:
        card = build_scorecard(_intent(), _session(), [])
        assert card.level == 1
        assert card.level_name == "Available"

    def test_swhid_gates_available(self) -> None:
        intent = _intent().model_copy(update={"swhid": ""})
        card = build_scorecard(intent, _session(), [])
        assert card.level == 0

    def test_built_and_inventoried_runtime_is_captured(self) -> None:
        card = build_scorecard(_intent(), _session(), [_build_receipt(), _sbom_receipt()])
        assert card.level == 2
        assert card.level_name == "Captured"

    def test_activation_pass_is_functional(self) -> None:
        receipts: list[RunReceipt] = [_build_receipt(), _sbom_receipt(), _activation_receipt()]
        card = build_scorecard(_intent(), _session(), receipts)
        assert card.level == 3
        assert card.level_name == "Functional"

    def test_all_experiments_validated_is_executed(self) -> None:
        card = build_scorecard(_intent(), _session(), _full_receipts())
        assert card.level == 4
        assert card.level_name == "Executed"

    def test_sealed_with_everything_included_is_archived(self) -> None:
        card = build_scorecard(_intent(), _sealed_session(), _full_receipts())
        assert card.level == 5
        assert card.level_name == "Archived"
        assert card.sealed

    def test_seal_does_not_launder_missing_reproduction(self) -> None:
        # Sealed with everything bundled, but activation never ran: the ladder
        # stops at Captured — publishing must not upgrade the claim.
        receipts: list[RunReceipt] = [_build_receipt(), _sbom_receipt(), _experiment_receipt("fig1")]
        card = build_scorecard(_intent(), _sealed_session(), receipts)
        assert card.level == 2

    def test_no_experiments_caps_at_functional(self) -> None:
        intent = _intent(experiments=[])
        receipts: list[RunReceipt] = [_build_receipt(), _sbom_receipt(), _activation_receipt()]
        card = build_scorecard(intent, _sealed_session(), receipts)
        assert card.level == 3

    def test_level_names_cover_the_ladder(self) -> None:
        assert len(LEVEL_NAMES) == 6


class TestDigestChains:
    def test_stale_sbom_does_not_count(self) -> None:
        # SBOM taken from an older runtime build: inventoried must not hold.
        receipts: list[RunReceipt] = [_build_receipt(), _sbom_receipt(declared=_OTHER_DIGEST)]
        card = build_scorecard(_intent(), _session(), receipts)
        assert not _rung(card, "runtime", "inventoried").reached
        assert card.level == 1

    def test_stale_activation_does_not_count(self) -> None:
        receipts: list[RunReceipt] = [
            _build_receipt(),
            _sbom_receipt(),
            _activation_receipt(declared=_OTHER_DIGEST),
        ]
        card = build_scorecard(_intent(), _session(), receipts)
        assert not _rung(card, "activation", "passed").reached
        assert card.level == 2

    def test_digestless_legacy_receipts_stay_acceptable(self) -> None:
        receipts: list[RunReceipt] = [
            _build_receipt(digest=None),
            _sbom_receipt(declared=None),
            _activation_receipt(declared=None),
        ]
        card = build_scorecard(_intent(), _session(), receipts)
        assert _rung(card, "activation", "passed").reached

    def test_stale_experiment_run_does_not_validate(self) -> None:
        receipts: list[RunReceipt] = [
            _build_receipt(),
            _sbom_receipt(),
            _activation_receipt(),
            _experiment_receipt("fig1", declared=_OTHER_DIGEST),
        ]
        card = build_scorecard(_intent(), _session(), receipts)
        assert _rung(card, "experiments", "validated").done == 0
        assert card.level == 3


class TestCategories:
    def test_experiment_fractions(self) -> None:
        intent = _intent(
            experiments=[
                Experiment(name="fig1", output_paths=["a.csv"]),
                Experiment(name="fig2", output_paths=["b.csv"]),
            ]
        )
        receipts: list[RunReceipt] = [_build_receipt(), _experiment_receipt("fig1")]
        card = build_scorecard(intent, _session(), receipts)
        validated = _rung(card, "experiments", "validated")
        assert (validated.done, validated.total, validated.reached) == (1, 2, False)
        captured = _rung(card, "results", "captured")
        assert (captured.done, captured.total, captured.reached) == (1, 2, False)

    def test_declared_outputs_require_captured_digest(self) -> None:
        receipts: list[RunReceipt] = [_build_receipt(), _experiment_receipt("fig1", output_digest=None)]
        card = build_scorecard(_intent(), _session(), receipts)
        assert _rung(card, "experiments", "validated").done == 0
        assert not _rung(card, "results", "captured").reached

    def test_failed_runs_are_ignored(self) -> None:
        receipts: list[RunReceipt] = [_build_receipt(), _experiment_receipt("fig1", status="failed")]
        card = build_scorecard(_intent(), _session(), receipts)
        assert _rung(card, "experiments", "validated").done == 0

    def test_skipped_runtime_is_not_available(self) -> None:
        intent = _intent().model_copy(update={"runtime": "__skipped__"})
        card = build_scorecard(intent, _session(), [])
        assert not _rung(card, "runtime", "available").reached

    def test_built_runtime_implies_available(self) -> None:
        intent = _intent().model_copy(update={"runtime": None})
        card = build_scorecard(intent, _session(), [_build_receipt()])
        assert _rung(card, "runtime", "available").reached

    def test_upload_counts_as_linked(self) -> None:
        intent = ReeIntent()
        session = ReeSession(uploaded_archive="paper.tar.gz")
        card = build_scorecard(intent, session, [])
        assert _rung(card, "source", "linked").reached


class TestCrossCheckRung:
    def test_cross_check_reaches_with_matching_sbom_digest(self) -> None:
        receipts: list[RunReceipt] = [_build_receipt(), _sbom_receipt(), _crosscheck_receipt()]
        card = build_scorecard(_intent(), _session(), receipts)
        rung = _rung(card, "runtime", "cross_checked")
        assert rung.reached
        assert (rung.done, rung.total) == (3, 4)

    def test_cross_check_against_stale_sbom_does_not_count(self) -> None:
        # The receipt cites a different SBOM than the one in evidence.
        receipts: list[RunReceipt] = [
            _build_receipt(),
            _sbom_receipt(),
            _crosscheck_receipt(sbom_digest="sha256:" + "f" * 64),
        ]
        card = build_scorecard(_intent(), _session(), receipts)
        assert not _rung(card, "runtime", "cross_checked").reached

    def test_cross_check_requires_an_inventoried_runtime(self) -> None:
        # SBOM from an older build: inventoried fails, so cross-checked must too.
        receipts: list[RunReceipt] = [
            _build_receipt(),
            _sbom_receipt(declared=_OTHER_DIGEST),
            _crosscheck_receipt(),
        ]
        card = build_scorecard(_intent(), _session(), receipts)
        assert not _rung(card, "runtime", "cross_checked").reached

    def test_missing_cross_check_leaves_fraction_unset(self) -> None:
        card = build_scorecard(_intent(), _session(), [_build_receipt(), _sbom_receipt()])
        rung = _rung(card, "runtime", "cross_checked")
        assert not rung.reached
        assert (rung.done, rung.total) == (None, None)

    def test_rung_is_non_gating(self) -> None:
        # R5 holds with everything else in place and no cross-check at all.
        card = build_scorecard(_intent(), _sealed_session(), _full_receipts())
        assert card.level == 5


class TestWireContract:
    def test_serializes_camel_case_with_derived_labels(self) -> None:
        card = build_scorecard(_intent(), _sealed_session(), _full_receipts())
        raw = json.loads(card.model_dump_json(by_alias=True))
        assert raw["schema_version"] == 1
        assert raw["level_code"] == "R5"
        assert raw["level_name"] == "Archived"
        assert [category["key"] for category in raw["categories"]] == [
            "source",
            "runtime",
            "activation",
            "experiments",
            "results",
        ]
        validated = next(c for c in raw["categories"] if c["key"] == "experiments")["rungs"][0]
        assert {"key", "label", "reached", "detail", "done", "total"} <= set(validated)
