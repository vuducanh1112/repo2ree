from __future__ import annotations

from dataclasses import replace

import pytest
from ree_definitions import LAUNCH, PLACEHOLDER, ree_definition

from repo2ree_core.domain.ree.audit import _evidence_standing, _Subject, audit
from repo2ree_core.domain.ree.transitions import commit_receipt, replace_definition
from repo2ree_protocol.audit import _STEP_FIELDS, ReeAudit
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.hbom import HBOM
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    BundleContents,
    BundleEntry,
    ExperimentDefinition,
    ExperimentEnvironmentDefinition,
    Ree,
    ReeSubject,
    SourceDefinition,
)
from repo2ree_ree.primitives import (
    Digest,
    ExperimentEnvironmentPath,
    OverlayPath,
    ReePath,
    RunId,
    parse_utc_instant,
)
from repo2ree_ree.receipt import (
    AcquireSourceReceipt,
    BuildExperimentEnvironmentReceipt,
    CrossCheckSbomReceipt,
    EvaluateReproducibilityReceipt,
    GenerateSbomReceipt,
    ObserveHardwareReceipt,
    RunExperimentReceipt,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)

_DIGEST = digest_bytes(b"content")
_OTHER_DIGEST = digest_bytes(b"other")
_EXPERIMENT_ENVIRONMENT_DIGEST = digest_bytes(b"experiment_environment")
_SBOM_DIGEST = digest_bytes(b"sbom")
_REPORT_DIGEST = digest_bytes(b"report")
_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SOURCE = SourceDefinition(origin_url="https://example.test/repo.tar.gz", source_type="tarball")
_EXPERIMENT_ENVIRONMENT_PATH = ExperimentEnvironmentPath("runtime.tar")
_EXPERIMENT_NAME = "demo"


def _source_receipt(snapshot_digest: Digest = _DIGEST) -> AcquireSourceReceipt:
    return AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url=_SOURCE.origin_url,
        source_type=_SOURCE.source_type,
        snapshot_digest=snapshot_digest,
    )


def _build_receipt(script_digest: Digest = _DIGEST) -> BuildExperimentEnvironmentReceipt:
    return BuildExperimentEnvironmentReceipt(
        run_id=RunId("build-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        snapshot_digest=_DIGEST,
        build_experiment_environment_script_path=OverlayPath(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
        build_experiment_environment_script_digest=script_digest,
        artifact_path=_EXPERIMENT_ENVIRONMENT_PATH,
        produced_artifact_digest=_EXPERIMENT_ENVIRONMENT_DIGEST,
        launch_script_digest=LAUNCH,
    )


def _experiment(name: str = _EXPERIMENT_NAME, *, run_script_digest: Digest = _DIGEST) -> ExperimentDefinition:
    return ExperimentDefinition(
        name=name,
        run_script_path=OverlayPath(experiment_run_script_path(name)),
        run_script_digest=run_script_digest,
        run_script_size=1,
        verify_script_path=OverlayPath(experiment_verify_script_path(name)),
        verify_script_digest=PLACEHOLDER,
        verify_script_size=1,
    )


def _experiment_receipt(name: str = _EXPERIMENT_NAME) -> RunExperimentReceipt:
    return RunExperimentReceipt(
        run_id=RunId("experiment-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        experiment_name=name,
        snapshot_digest=_DIGEST,
        experiment_environment_digest=_EXPERIMENT_ENVIRONMENT_DIGEST,
        activate_experiment_environment_script_digest=_DIGEST,
        run_script_digest=_DIGEST,
        launch_script_digest=LAUNCH,
        verify_script_digest=PLACEHOLDER,
    )


def _built_ree(*, build_experiment_environment_script_digest: Digest = _DIGEST) -> Ree:
    ree = Ree(
        subject=ReeSubject(
            definition=ree_definition(
                source=_SOURCE,
                experiment_environment=ExperimentEnvironmentDefinition(
                    build_experiment_environment_script_digest=build_experiment_environment_script_digest,
                    build_experiment_environment_script_size=1,
                    artifact_path=_EXPERIMENT_ENVIRONMENT_PATH,
                ),
                activate_experiment_environment=ActivateExperimentEnvironmentDefinition(
                    activate_experiment_environment_script_digest=_DIGEST,
                    activate_experiment_environment_script_size=1,
                ),
            )
        )
    )
    return commit_receipt(
        commit_receipt(ree, _source_receipt()), _build_receipt(build_experiment_environment_script_digest)
    )


def test_a_receipt_matching_what_the_ree_declares_is_current() -> None:
    result = audit(_built_ree())

    assert result.acquire_source.evidence == "current"
    assert result.build_experiment_environment.evidence == "current"
    assert result.stale_steps() == ()


def test_editing_the_build_experiment_environment_script_leaves_the_build_receipt_stale_and_says_why() -> None:
    ree = _built_ree()
    edited = replace_definition(
        ree,
        ree.subject.definition.model_copy(
            update={
                "experiment_environment": ExperimentEnvironmentDefinition(
                    build_experiment_environment_script_digest=_OTHER_DIGEST,
                    build_experiment_environment_script_size=2,
                    artifact_path=ExperimentEnvironmentPath("runtime.tar"),
                )
            }
        ),
    )

    experiment_environment = audit(edited).build_experiment_environment
    assert experiment_environment.evidence == "stale"
    assert experiment_environment.reasons == ("build experiment environment script changed",)
    assert experiment_environment.receipt_run_id == RunId("build-1")


def test_repointing_the_source_leaves_the_source_receipt_stale() -> None:
    ree = _built_ree()
    repointed = replace_definition(
        ree,
        ree.subject.definition.model_copy(
            update={"source": _SOURCE.model_copy(update={"origin_url": "https://example.test/other.tar.gz"})}
        ),
    )

    assert audit(repointed).acquire_source.reasons == ("source origin changed",)


def test_stale_steps_names_every_stale_step_including_experiments() -> None:
    ree = commit_receipt(
        replace_definition(
            _built_ree(),
            _built_ree().subject.definition.model_copy(update={"experiments": (_experiment(),)}),
        ),
        _experiment_receipt(),
    )
    assert audit(ree).stale_steps() == ()

    definition = ree.subject.definition
    edited = replace_definition(
        ree,
        definition.model_copy(
            update={
                "experiment_environment": ExperimentEnvironmentDefinition(
                    build_experiment_environment_script_digest=_OTHER_DIGEST,
                    build_experiment_environment_script_size=2,
                    artifact_path=ExperimentEnvironmentPath("runtime.tar"),
                ),
                "experiments": (_experiment(run_script_digest=_OTHER_DIGEST),),
            }
        ),
    )

    stale = audit(edited).stale_steps()

    assert [name for name, _ in stale] == ["build_experiment_environment", f"experiment '{_EXPERIMENT_NAME}'"]
    assert [step.reasons for _, step in stale] == [
        ("build experiment environment script changed",),
        ("experiment run script changed",),
    ]


def _cross_checked_ree(
    *,
    sbom_digest: Digest = _SBOM_DIGEST,
    report_digest: Digest = _REPORT_DIGEST,
) -> Ree:
    ree = _built_ree()
    ree = commit_receipt(
        ree,
        EvaluateReproducibilityReceipt(
            run_id=RunId("evaluation-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            snapshot_digest=_DIGEST,
            overlay_digest=_DIGEST,
            strict=False,
            dependency_level=1,
            environment_level=1,
            machine_level=0,
            dependency_count=1,
            manifest_count=1,
            report_digest=_REPORT_DIGEST,
            analyzer_version="1",
        ),
    )
    ree = commit_receipt(
        ree,
        GenerateSbomReceipt(
            run_id=RunId("sbom-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            experiment_environment_path=_EXPERIMENT_ENVIRONMENT_PATH,
            experiment_environment_digest=_EXPERIMENT_ENVIRONMENT_DIGEST,
            sbom_digest=_SBOM_DIGEST,
            sbom_format="cyclonedx",
            tool_version="1",
        ),
    )
    return commit_receipt(
        ree,
        CrossCheckSbomReceipt(
            run_id=RunId("cross-check-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            sbom_digest=sbom_digest,
            report_digest=report_digest,
            declared_direct_total=1,
            observed_matched=1,
            version_mismatches=0,
            undeclared_same_ecosystem=0,
            observed_total=1,
        ),
    )


def test_a_cross_check_over_the_current_documents_is_current() -> None:
    assert audit(_cross_checked_ree()).cross_check_sbom.evidence == "current"


def test_regenerating_either_cross_checked_document_leaves_the_cross_check_stale() -> None:
    rescanned = audit(_cross_checked_ree(sbom_digest=_OTHER_DIGEST)).cross_check_sbom
    reevaluated = audit(_cross_checked_ree(report_digest=_OTHER_DIGEST)).cross_check_sbom

    assert rescanned.reasons == ("SBOM changed",)
    assert reevaluated.reasons == ("reproducibility report changed",)
    assert {rescanned.evidence, reevaluated.evidence} == {"stale"}


def test_a_stale_cross_check_reaches_the_seal_gate() -> None:
    stale = audit(_cross_checked_ree(sbom_digest=_OTHER_DIGEST)).stale_steps()

    assert [name for name, _ in stale] == ["cross_check_sbom"]


def test_stale_steps_walks_every_step_the_audit_reports() -> None:
    reported = set(ReeAudit.model_fields) - {"reproducibility"}

    assert reported == {"experiments", *_STEP_FIELDS}


def test_removing_the_source_declaration_leaves_its_receipt_stale() -> None:
    orphaned = replace_definition(
        _built_ree(),
        _built_ree().subject.definition.model_copy(update={"source": None}),
    )

    result = audit(orphaned)

    assert result.acquire_source.evidence == "stale"
    assert result.acquire_source.reasons == ("the REE no longer declares what this evidence is about",)
    assert "acquire_source" in {name for name, _ in result.stale_steps()}


def test_a_step_with_neither_declaration_nor_receipt_stays_not_applicable() -> None:
    bare = Ree(subject=ReeSubject(definition=ree_definition()))

    result = audit(bare)

    assert result.build_experiment_environment.evidence == "not_applicable"
    assert result.build_experiment_environment.reasons == ()
    assert result.stale_steps() == ()


@pytest.mark.parametrize(
    ("applicable", "has_receipt", "complaints", "expected"),
    [
        (False, False, False, "not_applicable"),
        (True, False, False, "missing"),
        (True, True, False, "current"),
        (True, True, True, "stale"),
        (False, True, False, "stale"),
        (False, True, True, "stale"),
    ],
)
def test_evidence_standing_is_the_table_it_documents(
    applicable: bool,
    has_receipt: bool,
    complaints: bool,
    expected: str,
) -> None:
    assert _evidence_standing(applicable=applicable, has_receipt=has_receipt, complaints=complaints) == expected


def test_an_observed_hardware_receipt_stands_without_a_declaration() -> None:
    observed = commit_receipt(
        _built_ree(),
        ObserveHardwareReceipt(
            run_id=RunId("hbom-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            observation=HBOM(),
            observer_version="1",
        ),
    )

    result = audit(observed)

    assert observed.subject.definition.hbom is None
    assert result.observe_hardware.evidence == "current"
    assert result.stale_steps() == ()


def test_hardware_is_not_applicable_when_neither_declared_nor_observed() -> None:
    assert audit(_built_ree()).observe_hardware.evidence == "not_applicable"


def test_a_hardware_declaration_that_lists_nothing_requires_no_observation() -> None:
    empty = replace_definition(_built_ree(), _built_ree().subject.definition.model_copy(update={"hbom": HBOM()}))
    assert audit(empty).observe_hardware.evidence == "not_applicable"
    cpu = HBOM.model_validate({"cpus": {"Xeon": {"quantity": 2}}})
    declared = replace_definition(_built_ree(), _built_ree().subject.definition.model_copy(update={"hbom": cpu}))
    assert audit(declared).observe_hardware.evidence == "missing"


def _sealed_with(*paths: str) -> Ree:
    ree = _built_ree()
    contents = BundleContents(
        entries=tuple(BundleEntry(path=ReePath(path), digest=_OTHER_DIGEST, size=1) for path in sorted(paths))
    )
    return ree.model_copy(update={"subject": ree.subject.model_copy(update={"contents": contents})})


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        ((f"results/{_EXPERIMENT_NAME}/results/run.log",), "present"),
        (("results/another/results/run.log",), "omitted"),
        ((), "omitted"),
    ],
)
def test_an_experiments_outputs_are_present_when_they_travel_in_the_archive(
    paths: tuple[str, ...], expected: str
) -> None:
    subject = _Subject.of(_sealed_with(*paths))
    assert replace(subject, bundle_settled=True).experiment_payload(_EXPERIMENT_NAME, applicable=True) == expected


def test_editing_the_activate_script_leaves_what_ran_through_it_stale_but_not_the_build() -> None:
    ree = commit_receipt(
        replace_definition(
            _built_ree(),
            _built_ree().subject.definition.model_copy(update={"experiments": (_experiment(),)}),
        ),
        _experiment_receipt(),
    )
    edited = replace_definition(
        ree,
        ree.subject.definition.model_copy(
            update={
                "activate_experiment_environment": ActivateExperimentEnvironmentDefinition(
                    activate_experiment_environment_script_digest=_OTHER_DIGEST,
                    activate_experiment_environment_script_size=2,
                )
            }
        ),
    )

    result = audit(edited)

    assert result.build_experiment_environment.evidence == "current"
    assert result.experiments[0].run.reasons == ("activate experiment environment script changed",)


def test_an_evaluation_rests_on_the_source_alone_so_rewriting_a_script_leaves_it_current() -> None:
    evaluated = _cross_checked_ree()
    definition = evaluated.subject.definition
    rewritten = definition.model_copy(
        update={"launch": definition.launch.model_copy(update={"launch_script_digest": _OTHER_DIGEST})}
    )
    assert audit(replace_definition(evaluated, rewritten)).evaluate_reproducibility.evidence == "current"
