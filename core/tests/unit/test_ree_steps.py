"""Where an REE stands on each authoring step, judged from its own records."""

from __future__ import annotations

from ree_definitions import PLACEHOLDER, bare_ree, ree_definition

from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.steps import REE_STEPS, ree_steps
from repo2ree_protocol.audit import ReeAudit, StepAudit
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
        source=step("source"),
        evaluation=step("evaluation"),
        hardware=step("hardware"),
        working_environment_check=step("working_environment_check"),
        experiment_environment=step("experiment_environment"),
        sbom=step("sbom"),
        sbom_cross_check=step("sbom_cross_check"),
        activation=step("activation"),
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

    assert steps.next == "source"
    assert statuses["source"] == "ready"
    assert statuses["evaluate"] == "blocked"
    assert statuses["crosscheck"] == "blocked"
    assert "complete" not in statuses.values()


def test_a_current_receipt_completes_its_step_and_readies_what_needs_it() -> None:
    statuses = _statuses(bare_ree(), _audit_with(source=True, experiment_environment=True))

    assert statuses["source"] == "complete"
    assert statuses["build_experiment_environment"] == "complete"
    assert statuses["evaluate"] == "ready"
    assert statuses["sbom"] == "ready"
    assert statuses["crosscheck"] == "blocked"


def test_a_stale_receipt_completes_nothing() -> None:
    stale = _audit_with(source=True).model_copy(
        update={"experiment_environment": StepAudit(evidence="stale", payload="not_applicable")}
    )
    statuses = _statuses(bare_ree(), stale)

    assert statuses["build_experiment_environment"] == "ready"
    assert statuses["sbom"] == "blocked"


def test_the_next_step_is_the_first_ready_one() -> None:
    assert ree_steps(bare_ree(), _audit_with(source=True)).next == "metadata"


def test_metadata_needs_a_name_a_version_and_a_description() -> None:
    partial = ree_definition(name="demo", catalog=ReeCatalogMetadata(version="1.0"))
    whole = ree_definition(name="demo", catalog=ReeCatalogMetadata(version="1.0", description="A demo."))

    assert _statuses(_with(partial))["metadata"] == "ready"
    assert _statuses(_with(whole))["metadata"] == "complete"


def test_hardware_is_described_once_it_names_a_component() -> None:
    described = ree_definition(hardware=HardwareDefinition(cpus={"Xeon": CPUDefinition(quantity=2)}))

    assert _statuses(_with(ree_definition(hardware=HardwareDefinition())))["hbom"] == "ready"
    assert _statuses(_with(described))["hbom"] == "complete"


def test_experiments_are_complete_once_one_is_declared() -> None:
    experiment = ExperimentDefinition(
        name="demo",
        run_script_path=OverlayPath(experiment_run_script_path("demo")),
        run_script_digest=digest_bytes(b"run"),
        run_script_size=3,
        verify_script_path=OverlayPath(experiment_verify_script_path("demo")),
        verify_script_digest=PLACEHOLDER,
        verify_script_size=1,
    )

    assert _statuses(_with(ree_definition(experiments=(experiment,))))["experiments"] == "complete"


def test_a_sealed_ree_has_completed_its_seal() -> None:
    subject = ReeSubject(definition=ree_definition())
    sealed = Ree(
        subject=subject,
        seal=ReeSeal(sealed_at=parse_utc_instant("2026-11-15T00:00:00Z"), ree_digest=canonical_subject_digest(subject)),
    )

    assert _statuses(sealed)["seal"] == "complete"
