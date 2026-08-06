"""What the audit says about receipts the REE has since moved out from under."""

from __future__ import annotations

import pytest

from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.domain.primitives import Digest, ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.audit import _STEP_FIELDS, ReeAudit, _evidence_standing, audit
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    ExperimentDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    SourceDefinition,
)
from repo2ree_core.domain.ree.receipt import (
    AcquireSourceReceipt,
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    EvaluateReproducibilityReceipt,
    GenerateSbomReceipt,
    ObserveHardwareReceipt,
    RunExperimentReceipt,
    WorkspaceDrift,
)
from repo2ree_core.domain.ree.transitions import commit_receipt, replace_definition
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT, experiment_run_script_path

_DIGEST = digest_bytes(b"content")
_OTHER_DIGEST = digest_bytes(b"other")
_RUNTIME_DIGEST = digest_bytes(b"runtime")
_SBOM_DIGEST = digest_bytes(b"sbom")
_REPORT_DIGEST = digest_bytes(b"report")
_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_SOURCE = SourceDefinition(origin_url="https://example.test/repo.git", source_type="git")
_RUNTIME_PATH = WorkspacePath("runtime.tar")
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


def _build_receipt(script_digest: Digest = _DIGEST) -> BuildRuntimeReceipt:
    return BuildRuntimeReceipt(
        run_id=RunId("build-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        snapshot_digest=_DIGEST,
        build_runtime_script_path=ReePath(RESERVED_BUILD_SCRIPT),
        build_runtime_script_digest=script_digest,
        workspace_drift=WorkspaceDrift(status="clean"),
        runtime_path=_RUNTIME_PATH,
        produced_runtime_digest=_RUNTIME_DIGEST,
    )


def _experiment(name: str = _EXPERIMENT_NAME, *, run_script_digest: Digest = _DIGEST) -> ExperimentDefinition:
    return ExperimentDefinition(
        name=name,
        run_script_path=ReePath(experiment_run_script_path(name)),
        run_script_digest=run_script_digest,
        run_script_size=1,
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
        runtime_digest=_RUNTIME_DIGEST,
        run_script_digest=_DIGEST,
    )


def _built_ree(*, build_script_digest: Digest = _DIGEST) -> Ree:
    ree = Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                source=_SOURCE,
                build_runtime=BuildRuntimeDefinition(
                    build_runtime_script_digest=build_script_digest,
                    build_runtime_script_size=1,
                    runtime_path=_RUNTIME_PATH,
                ),
            )
        )
    )
    return commit_receipt(commit_receipt(ree, _source_receipt()), _build_receipt(build_script_digest))


def test_a_receipt_matching_what_the_ree_declares_is_current() -> None:
    result = audit(_built_ree())

    assert result.source.evidence == "current"
    assert result.runtime.evidence == "current"
    assert result.stale_steps() == ()


def test_editing_the_build_script_leaves_the_build_receipt_stale_and_says_why() -> None:
    ree = _built_ree()
    edited = replace_definition(
        ree,
        ree.subject.definition.model_copy(
            update={
                "build_runtime": BuildRuntimeDefinition(
                    build_runtime_script_digest=_OTHER_DIGEST,
                    build_runtime_script_size=2,
                    runtime_path=WorkspacePath("runtime.tar"),
                )
            }
        ),
    )

    runtime = audit(edited).runtime
    assert runtime.evidence == "stale"
    assert runtime.reasons == ("runtime build script changed",)
    # The receipt is kept, not deleted: it is still what that run recorded.
    assert runtime.receipt_run_id == RunId("build-1")


def test_repointing_the_source_leaves_the_source_receipt_stale() -> None:
    ree = _built_ree()
    repointed = replace_definition(
        ree,
        ree.subject.definition.model_copy(
            update={"source": _SOURCE.model_copy(update={"origin_url": "https://example.test/other.git"})}
        ),
    )

    assert audit(repointed).source.reasons == ("source origin changed",)


def test_stale_steps_names_every_stale_step_including_experiments() -> None:
    ree = commit_receipt(
        replace_definition(
            _built_ree(),
            _built_ree().subject.definition.model_copy(update={"experiments": (_experiment(),)}),
        ),
        _experiment_receipt(),
    )
    assert audit(ree).stale_steps() == ()

    # Edit both the build script and the experiment's run script.
    definition = ree.subject.definition
    edited = replace_definition(
        ree,
        definition.model_copy(
            update={
                "build_runtime": BuildRuntimeDefinition(
                    build_runtime_script_digest=_OTHER_DIGEST,
                    build_runtime_script_size=2,
                    runtime_path=WorkspacePath("runtime.tar"),
                ),
                "experiments": (_experiment(run_script_digest=_OTHER_DIGEST),),
            }
        ),
    )

    stale = audit(edited).stale_steps()

    assert [name for name, _ in stale] == ["runtime", f"experiment '{_EXPERIMENT_NAME}'"]
    assert [step.reasons for _, step in stale] == [
        ("runtime build script changed",),
        ("experiment run script changed",),
    ]


def _cross_checked_ree(
    *,
    sbom_digest: Digest = _SBOM_DIGEST,
    report_digest: Digest = _REPORT_DIGEST,
) -> Ree:
    """A built REE whose SBOM has been generated, evaluated, and cross-checked.

    The checked ``sbom_digest`` / ``report_digest`` are the cross-check's view
    of its two inputs; passing a different one is how a test says "that
    document was regenerated after the cross-check ran".
    """
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
            runtime_path=_RUNTIME_PATH,
            runtime_digest=_RUNTIME_DIGEST,
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
    assert audit(_cross_checked_ree()).sbom_cross_check.evidence == "current"


def test_regenerating_either_cross_checked_document_leaves_the_cross_check_stale() -> None:
    rescanned = audit(_cross_checked_ree(sbom_digest=_OTHER_DIGEST)).sbom_cross_check
    reevaluated = audit(_cross_checked_ree(report_digest=_OTHER_DIGEST)).sbom_cross_check

    assert rescanned.reasons == ("SBOM changed",)
    assert reevaluated.reasons == ("reproducibility report changed",)
    assert {rescanned.evidence, reevaluated.evidence} == {"stale"}


def test_a_stale_cross_check_reaches_the_seal_gate() -> None:
    """It is a step like any other: the generic walk must pick it up."""
    stale = audit(_cross_checked_ree(sbom_digest=_OTHER_DIGEST)).stale_steps()

    assert [name for name, _ in stale] == ["sbom_cross_check"]


def test_stale_steps_walks_every_step_the_audit_reports() -> None:
    """A step added to ``ReeAudit`` must be reachable from ``stale_steps``.

    Seal refuses on what this walk finds, so a step it does not reach is a step
    whose staleness would be published as though it held.
    """
    reported = set(ReeAudit.model_fields) - {"reproducibility"}

    assert reported == {"experiments", *_STEP_FIELDS}


# ================================================
# Receipts that outlive their declaration
# ================================================


def test_removing_the_build_declaration_leaves_its_receipt_stale_rather_than_hidden() -> None:
    """Deleting ``build.sh`` drops the declaration but keeps the receipt.

    The receipt then attests a build of a recipe the REE no longer carries.
    Reporting that as ``not_applicable`` would hide it from the seal gate,
    which is the one reader that must not miss it.
    """
    orphaned = replace_definition(
        _built_ree(),
        _built_ree().subject.definition.model_copy(update={"build_runtime": None}),
    )

    result = audit(orphaned)

    assert result.runtime.evidence == "stale"
    assert result.runtime.receipt_run_id == RunId("build-1")
    assert result.runtime.reasons == ("runtime build definition was removed",)
    assert [name for name, _ in result.stale_steps()] == ["runtime"]


def test_removing_the_source_declaration_leaves_its_receipt_stale() -> None:
    """The steps whose comparisons all pass vacuously get the generic reason."""
    orphaned = replace_definition(
        _built_ree(),
        _built_ree().subject.definition.model_copy(update={"source": None}),
    )

    result = audit(orphaned)

    assert result.source.evidence == "stale"
    assert result.source.reasons == ("the REE no longer declares what this evidence is about",)
    assert "source" in {name for name, _ in result.stale_steps()}


def test_a_step_with_neither_declaration_nor_receipt_stays_not_applicable() -> None:
    bare = Ree(subject=ReeSubject(definition=ReeDefinition()))

    result = audit(bare)

    assert result.runtime.evidence == "not_applicable"
    assert result.runtime.reasons == ()
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
    """Pin the classification itself, apart from which comparisons feed it."""
    assert _evidence_standing(applicable=applicable, has_receipt=has_receipt, complaints=complaints) == expected


def test_an_observed_hardware_receipt_stands_without_a_declaration() -> None:
    """The observation is the content, not evidence for something declared.

    ``generate_hbom`` files this receipt and never declares
    ``definition.hardware`` — an author may observe the machine without stating
    a requirement. Reading that as an orphan would refuse the seal on a
    perfectly consistent REE.
    """
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

    assert observed.subject.definition.hardware is None
    assert result.hardware.evidence == "current"
    assert result.stale_steps() == ()


def test_hardware_is_not_applicable_when_neither_declared_nor_observed() -> None:
    assert audit(_built_ree()).hardware.evidence == "not_applicable"
