from __future__ import annotations

from ree_definitions import PLACEHOLDER, bare_ree, ree_definition

from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import REE_STEPS, ree_steps
from repo2ree_protocol.audit import EvidenceStatus, ExperimentAudit, ReeAudit, StepAudit
from repo2ree_protocol.catalog import ReeStepStatus
from repo2ree_protocol.verbs import VERBS
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.hbom import CPUDefinition
from repo2ree_ree.model import (
    ExperimentDefinition,
    HardwareDefinition,
    Ree,
    ReeCatalogMetadata,
    ReeDefinition,
    ReeSeal,
    ReeSubject,
    canonical_subject_digest,
)
from repo2ree_ree.primitives import OverlayPath, parse_utc_instant
from repo2ree_ree.reserved_paths import experiment_run_script_path, experiment_verify_script_path


def _statuses(ree: Ree, ree_audit: ReeAudit | None = None) -> dict[str, ReeStepStatus]:
    return {step.key: step.status for step in ree_steps(ree, ree_audit or audit(ree)).steps}


def _with(definition: ReeDefinition) -> Ree:
    return Ree(subject=ReeSubject(definition=definition))


def _audit_with(**current: bool) -> ReeAudit:
    def step(name: str) -> StepAudit:
        return StepAudit(evidence="current" if current.get(name) else "missing", payload="not_applicable")

    return ReeAudit(
        acquire_source=step("acquire_source"),
        evaluate_reproducibility=step("evaluate_reproducibility"),
        observe_hardware=step("observe_hardware"),
        check_working_environment=step("check_working_environment"),
        build_experiment_environment=step("build_experiment_environment"),
        generate_sbom=step("generate_sbom"),
        cross_check_sbom=step("cross_check_sbom"),
        activate_experiment_environment=step("activate_experiment_environment"),
    )


def test_the_steps_follow_their_requirements_in_order() -> None:
    seen: set[str] = set()
    for step in REE_STEPS:
        assert set(step.requires) <= seen, f"{step.key} needs a step that comes after it"
        seen.add(step.key)
    assert [step.order for step in REE_STEPS] == list(range(1, len(REE_STEPS) + 1))


def test_every_command_a_step_names_is_a_ree_command() -> None:
    commands = {" ".join(words) for words in VERBS.values()}
    for step in REE_STEPS:
        assert step.commands, f"{step.key} names no command"
        assert set(step.commands) <= commands


def test_a_fresh_ree_starts_with_its_source() -> None:
    steps = ree_steps(bare_ree(), audit(bare_ree()))
    statuses = {step.key: step.status for step in steps.steps}

    assert steps.next == "acquire_source"
    assert statuses["acquire_source"] == "ready"
    assert statuses["evaluate_reproducibility"] == "blocked"
    assert statuses["cross_check_sbom"] == "blocked"
    assert "complete" not in statuses.values()


def test_a_current_receipt_completes_its_step_and_readies_what_needs_it() -> None:
    statuses = _statuses(bare_ree(), _audit_with(acquire_source=True, build_experiment_environment=True))

    assert statuses["acquire_source"] == "complete"
    assert statuses["build_experiment_environment"] == "complete"
    assert statuses["evaluate_reproducibility"] == "ready"
    assert statuses["generate_sbom"] == "ready"
    assert statuses["cross_check_sbom"] == "blocked"


def test_a_stale_receipt_completes_nothing() -> None:
    stale = _audit_with(acquire_source=True).model_copy(
        update={"build_experiment_environment": StepAudit(evidence="stale", payload="not_applicable")}
    )
    statuses = _statuses(bare_ree(), stale)

    assert statuses["build_experiment_environment"] == "ready"
    assert statuses["generate_sbom"] == "blocked"


def test_the_next_step_is_the_first_ready_one() -> None:
    assert ree_steps(bare_ree(), _audit_with(acquire_source=True)).next == "metadata"


def test_metadata_needs_a_name_a_version_and_a_description() -> None:
    partial = ree_definition(name="demo", catalog=ReeCatalogMetadata(version="1.0"))
    whole = ree_definition(name="demo", catalog=ReeCatalogMetadata(version="1.0", description="A demo."))

    assert _statuses(_with(partial))["metadata"] == "ready"
    assert _statuses(_with(whole))["metadata"] == "complete"


def test_hardware_is_described_once_it_names_a_component() -> None:
    described = ree_definition(hbom=HardwareDefinition(cpus={"Xeon": CPUDefinition(quantity=2)}))

    assert _statuses(_with(ree_definition(hbom=HardwareDefinition())))["observe_hardware"] == "ready"
    assert _statuses(_with(described))["observe_hardware"] == "complete"


def test_hardware_is_described_once_it_is_observed() -> None:
    assert _statuses(bare_ree(), _audit_with(observe_hardware=True))["observe_hardware"] == "complete"


def _experiment() -> ExperimentDefinition:
    return ExperimentDefinition(
        name="demo",
        run_script_path=OverlayPath(experiment_run_script_path("demo")),
        run_script_digest=digest_bytes(b"run"),
        run_script_size=3,
        verify_script_path=OverlayPath(experiment_verify_script_path("demo")),
        verify_script_digest=PLACEHOLDER,
        verify_script_size=1,
    )


def _experiment_audit(evidence: EvidenceStatus) -> ReeAudit:
    run = StepAudit(evidence=evidence, payload="not_applicable")
    built = _audit_with(acquire_source=True, build_experiment_environment=True, activate_experiment_environment=True)
    return built.model_copy(update={"experiments": (ExperimentAudit(name="demo", run=run),)})


def test_experiments_are_complete_once_each_declared_one_ran() -> None:
    ree = _with(ree_definition(experiments=(_experiment(),)))

    assert _statuses(ree, _experiment_audit("current"))["experiments"] == "complete"
    assert _statuses(ree, _experiment_audit("missing"))["experiments"] == "ready"
    assert _statuses(ree, _experiment_audit("stale"))["experiments"] == "ready"
    assert _statuses(bare_ree(), _experiment_audit("current"))["experiments"] == "ready"


def test_a_sealed_ree_has_completed_its_seal() -> None:
    subject = ReeSubject(definition=ree_definition())
    sealed = Ree(
        subject=subject,
        seal=ReeSeal(sealed_at=parse_utc_instant("2026-11-15T00:00:00Z"), ree_digest=canonical_subject_digest(subject)),
    )

    assert _statuses(sealed)["seal_ree"] == "complete"
    assert ree_steps(sealed, audit(sealed)).next is None
