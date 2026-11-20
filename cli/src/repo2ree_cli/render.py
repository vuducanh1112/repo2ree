"""What a person reads: each result ``ree`` prints, as plain lines.

``--json`` prints the same results as data; nothing here is read by a machine.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from typing import Any, get_args

from repo2ree_protocol.audit import ReeAudit, StepAudit
from repo2ree_protocol.catalog import ReeStepKey, ReeSteps, ReservedScriptTemplates, ScriptTemplateCatalog
from repo2ree_protocol.document import ReeStatusReport, WorkbenchReeDocument
from repo2ree_protocol.history import OperationHistory
from repo2ree_protocol.inference import InferenceReport, TargetInferenceResult
from repo2ree_protocol.outputs import (
    AcquireSourceOutputs,
    BuildExperimentEnvironmentOutputs,
    CrossCheckSbomOutputs,
    EvaluateOutputs,
    GenerateSbomOutputs,
    LoadReeBundleOutputs,
    ObserveHardwareOutputs,
    PatchReeDefinitionOutputs,
    RunnableOperationOutputs,
    SealOutputs,
    SignOutputs,
    SignReviewOutputs,
)
from repo2ree_ree.hbom import HBOM
from repo2ree_ree.receipt import ReceiptEnvelope
from repo2ree_ree.reproducibility import ReproducibilityReport, SbomCrossCheckSummary, Severity
from repo2ree_ree.review import ReviewRecord, ReviewSet
from repo2ree_ree.verification import SignatureVerifications

_MARKS = {"complete": "✓", "ready": "·", "blocked": "✗"}
_EVIDENCE = {"current": "current", "stale": "STALE", "missing": "missing", "not_applicable": "n/a"}

# What to run for each step, as a person types it.
HINTS: dict[ReeStepKey, str] = {
    "acquire_source": "ree acquire-source --archive PATH, or ree acquire-source --origin-url URL",
    "metadata": "ree patch-ree-definition --name NAME --version VERSION --description TEXT",
    "observe_hardware": "ree observe-hardware",
    "check_working_environment": "ree edit check_working_environment, then ree check-working-environment",
    "evaluate_reproducibility": "ree evaluate-reproducibility",
    "build_experiment_environment": (
        "ree patch-ree-definition --artifact-path PATH, "
        "ree suggest-scripts --target build_experiment_environment --write, then ree build-experiment-environment"
    ),
    "generate_sbom": "ree generate-sbom",
    "cross_check_sbom": "ree cross-check-sbom",
    "activate_experiment_environment": (
        "ree suggest-scripts --target activate_experiment_environment --write, then ree activate-experiment-environment"
    ),
    "experiments": (
        "ree patch-ree-definition --experiment NAME --output PATH, ree edit experiment_run:NAME, "
        "then ree run-experiment NAME"
    ),
    "seal_ree": "ree seal-ree",
}


def next_hint(steps: ReeSteps) -> str | None:
    """The line that says what to do next, or None when every step is complete."""
    following = next((step for step in steps.steps if step.key == steps.next), None)
    if following is None:
        return None
    return f"next: {following.label}: {HINTS[following.key]}"


def _closing(report: ReeStatusReport) -> str:
    if report.status != "sealed":
        return "every step is complete"
    if all(step.status == "complete" for step in report.steps.steps):
        return "sealed, with every step complete"
    return "sealed: it takes no further step; the open steps above are what its seal does not attest"


def status(report: ReeStatusReport) -> str:
    labels = {step.key: step.label for step in report.steps.steps}
    done = {step.key for step in report.steps.steps if step.status == "complete"}
    evidence = _step_evidence(report.audit)
    lines = [f"{report.name} ({report.status}, revision {report.revision})"]
    if report.running:
        lines.append(f"running: {report.running}")
    lines.append("")
    for step in report.steps.steps:
        mark = "→" if step.key == report.steps.next else _MARKS[step.status]
        line = f"{mark} {step.order:>2} {step.label}"
        audit = evidence.get(step.key)
        if audit is not None and audit.evidence == "stale":
            line += f"  STALE: {'; '.join(audit.reasons)}"
        if step.status == "blocked":
            line += f"  (needs {', '.join(labels[key] for key in step.requires if key not in done)})"
        lines.append(line)
    lines += [f"     experiment {item.name}: {_evidence_word(item.run)}" for item in report.audit.experiments]
    if report.drift:
        lines += ["", "changed outside ree, so the next command is refused:"]
        lines += [f"  {item.path}" for item in report.drift]
        lines.append("edit scripts in overlay/; `ree materialize-workspace` lays the workspace out again")
        return "\n".join(lines)
    lines += ["", next_hint(report.steps) or _closing(report)]
    return "\n".join(lines)


def _step_evidence(audit: ReeAudit) -> dict[ReeStepKey, StepAudit]:
    """Each step's evidence: a step keyed as an audited receipt is that receipt's."""
    return {key: step for key in get_args(ReeStepKey) if isinstance(step := getattr(audit, key, None), StepAudit)}


def _evidence_word(step: StepAudit) -> str:
    word = _EVIDENCE[step.evidence]
    return f"{word}: {'; '.join(step.reasons)}" if step.reasons and step.evidence == "stale" else word


def document(doc: WorkbenchReeDocument) -> str:
    definition = doc.ree.subject.definition
    receipts = doc.ree.subject.receipts
    lines = [f"{definition.name} ({doc.status})"]
    if definition.catalog.version or definition.catalog.description:
        lines.append(f"  {definition.catalog.version}  {definition.catalog.description}".rstrip())
    if doc.ree.seal is not None:
        lines.append(f"  sealed {doc.ree.seal.sealed_at}: {doc.ree.seal.ree_digest}")
    source = receipts.acquire_source
    if source is not None:
        origin = source.origin_url or "uploaded archive"
        lines.append(f"source: {source.source_type} from {origin}, {source.observed_swhid}")
    else:
        lines.append("source: none")
    environment = definition.experiment_environment
    if environment is not None and environment.artifact_path:
        lines.append(f"experiment environment: {environment.artifact_path}")
    for experiment in definition.experiments:
        outputs = ", ".join(str(path) for path in experiment.output_paths) or "no outputs declared"
        lines.append(f"experiment {experiment.name}: {outputs}")
    lines += ["", "evidence:"]
    named = (
        ("source", doc.audit.acquire_source),
        ("evaluation", doc.audit.evaluate_reproducibility),
        ("hardware", doc.audit.observe_hardware),
        ("working environment check", doc.audit.check_working_environment),
        ("experiment environment", doc.audit.build_experiment_environment),
        ("sbom", doc.audit.generate_sbom),
        ("sbom cross-check", doc.audit.cross_check_sbom),
        ("activation", doc.audit.activate_experiment_environment),
        *((f"experiment {item.name}", item.run) for item in doc.audit.experiments),
    )
    lines += [f"  {name}: {_evidence_word(step)}" for name, step in named]
    lines.append(f"\n{len(doc.ree_files)} files in the REE, {len(doc.workspace_files)} in its workspace")
    return "\n".join(lines)


def history(log: OperationHistory) -> str:
    if not log.operations:
        return "no attempts recorded"
    lines = []
    for record in log.operations:
        sequence = "" if record.sequence is None else str(record.sequence)
        scope = "" if record.scope == "." else f"  [{record.scope}]"
        failure = f": {record.operation_failure.message}" if record.operation_failure else ""
        operation = record.command.get("operation", "?")
        lines.append(
            f"{sequence:>4}  {operation:<36} {record.operation_status:<11} {record.run_id}{scope}{failure}".rstrip()
        )
    return "\n".join(lines)


def reviews(review_set: ReviewSet) -> str:
    if not review_set.reviews:
        return "no reviews"
    return "\n\n".join(review(record) for record in review_set.reviews)


def review(record: ReviewRecord) -> str:
    lines = [f"{record.review_id} ({record.status}, opened {record.created_at})"]
    if record.source_comparison is not None:
        source = record.source_comparison
        lines.append(f"  source: {source.verdict} ({source.basis})")
    if record.experiment_environment_comparison is not None:
        environment = record.experiment_environment_comparison
        lines.append(
            f"  experiment environment: {environment.verdict} ({environment.basis}; {environment.matched} matched, "
            f"{environment.missing_count} missing, {environment.extra_count} extra, "
            f"{environment.version_mismatch_count} versions differ)"
        )
    if record.activation_outcome is not None:
        lines.append(f"  activation: {record.activation_outcome.verdict} ({record.activation_outcome.basis})")
    lines += [f"  experiment {item.experiment_name}: {item.verdict}" for item in record.experiment_comparisons]
    if record.failure:
        lines.append(f"  failure: {record.failure}")
    return "\n".join(lines)


def templates(catalog: ScriptTemplateCatalog) -> str:
    sections = (
        catalog.check_working_environment,
        catalog.launch,
        catalog.build_experiment_environment,
        catalog.activate_experiment_environment,
        catalog.experiment_run,
        catalog.experiment_verify,
    )
    lines = []
    for section in sections:
        lines.append(section.path if isinstance(section, ReservedScriptTemplates) else section.path_pattern)
        lines += [
            f"  {entry.key:<24} {entry.label}{'  (default)' if entry.is_default else ''}" for entry in section.templates
        ]
    return "\n".join(lines)


def inference(report: InferenceReport, current: Mapping[str, str | None]) -> str:
    return "\n\n".join(_inferred(result, current.get(result.target.path)) for result in report.results)


def _inferred(result: TargetInferenceResult, current: str | None) -> str:
    lines = [f"{result.target.path}: {result.status.replace('_', ' ')}"]
    lines += [f"  ! {warning.message}" for warning in result.warnings]
    proposed = [candidate for candidate in result.candidates if candidate.body is not None]
    if not proposed:
        lines.append("  inference proposes no script here")
    for candidate in proposed:
        lines.append(f"\n  rule {candidate.inference_rule} ({candidate.status.replace('_', ' ')})")
        told = {warning.message for warning in result.warnings}
        lines += [f"  ! {warning.message}" for warning in candidate.warnings if warning.message not in told]
        body = candidate.body or ""
        if current == body:
            lines.append("  the script is already this")
        elif current is None:
            lines += [f"  + {line}" for line in body.splitlines()]
        else:
            diff = difflib.unified_diff(
                current.splitlines(), body.splitlines(), "written", "proposed", lineterm="", n=2
            )
            lines += [f"  {line}" for line in diff]
    return "\n".join(lines)


def acquired(outputs: AcquireSourceOutputs) -> str:
    origin = outputs.origin_url or outputs.archive_name or "an uploaded archive"
    return f"source: {outputs.source_type} from {origin}\n  {outputs.swhid or outputs.snapshot_digest}"


def patched(outputs: PatchReeDefinitionOutputs) -> str:
    return f"revision {outputs.revision}"


def evaluation(outputs: EvaluateOutputs) -> str:
    report = ReproducibilityReport.model_validate(outputs.report)
    summary = report.dependency_summary
    lines = [
        (
            f"dependencies  {report.dependency_level.label}: {summary.total} in "
            f"{_plural(summary.manifests, 'manifest')}"
            f"; {summary.pinned} pinned, {summary.ranged} ranged, {summary.unpinned} unpinned, {summary.locked} locked"
        ),
        f"environment   {report.environment_level.label}",
        f"machine       {report.machine_level.label}",
    ]
    if report.sbom_cross_check is not None:
        lines.append(f"sbom          {_cross_checked(report.sbom_cross_check)}")
    threats = sorted(report.threats, key=lambda threat: list(Severity).index(threat.severity))
    lines += ["", _plural(len(threats), "threat") if threats else "no threats"]
    lines += [f"  {threat.severity:<6}  {threat.title}: {threat.remediation}" for threat in threats]
    return "\n".join(lines)


def hardware(outputs: ObserveHardwareOutputs) -> str:
    observed = HBOM.model_validate(outputs.observation)
    lines = [
        *(
            f"cpu      {_count(cpu.quantity)}{name} ({cpu.architecture}, {_plural(cpu.cores_per_cpu, 'core')}, "
            f"{_plural(cpu.threads_per_core, 'thread')} per core)"
            for name, cpu in observed.cpus.items()
        ),
        *(f"gpu      {_count(gpu.quantity)}{name} ({_size(gpu.memory_bytes)})" for name, gpu in observed.gpus.items()),
        *(
            f"memory   {_count(memory.quantity)}{name} ({_size(memory.capacity_bytes)} {memory.memory_type})"
            for name, memory in observed.memory.items()
        ),
        *(
            f"storage  {_count(disk.quantity)}{name} ({_size(disk.capacity_bytes)} {disk.storage_type})"
            for name, disk in observed.storage.items()
        ),
        *(
            f"network  {_count(link.quantity)}{name} ({link.bandwidth_mbps} Mbps {link.network_type})"
            for name, link in observed.network.items()
        ),
    ]
    return "\n".join(lines) or "no hardware observed"


def ran(outputs: RunnableOperationOutputs) -> str:
    parts = []
    if outputs.exit_code is not None:
        parts.append(f"exit {outputs.exit_code}")
    if outputs.verify_exit_code is not None:
        parts.append(f"verify exit {outputs.verify_exit_code}")
    if outputs.verdict is not None:
        parts.append(outputs.verdict)
    return f"{outputs.subject_name}: {', '.join(parts) or 'ran'}{_took(outputs.receipt)}"


def built(outputs: BuildExperimentEnvironmentOutputs) -> str:
    receipt = outputs.receipt
    return (
        f"built {receipt.artifact_path}{_took(receipt)}\n  {receipt.produced_artifact_digest}\n"
        f"  workspace {receipt.workspace_drift.status}"
    )


def sbom(outputs: GenerateSbomOutputs) -> str:
    return (
        f"wrote {outputs.sbom_relative_path} ({outputs.format}) of {outputs.experiment_environment_relative_path}"
        f"{_took(outputs.receipt)}"
    )


def cross_checked(outputs: CrossCheckSbomOutputs) -> str:
    receipt = outputs.receipt
    return (
        f"{receipt.observed_matched} of {receipt.declared_direct_total} declared dependencies found in the sbom, "
        f"{receipt.version_mismatches} at another version\n"
        f"{receipt.undeclared_same_ecosystem} undeclared of {receipt.observed_total} packages observed"
    )


def _cross_checked(summary: SbomCrossCheckSummary) -> str:
    return (
        f"{summary.observed_matched} of {summary.declared_direct_total} declared found, "
        f"{summary.version_mismatches} at another version, {summary.undeclared_same_ecosystem} undeclared"
    )


def sealed(outputs: SealOutputs) -> str:
    return f"sealed {outputs.ree_digest}\n  {outputs.entry_count} entries, {_size(outputs.input_bytes)}"


def signed(outputs: SignOutputs | SignReviewOutputs) -> str:
    what = f"review {outputs.review_id}" if isinstance(outputs, SignReviewOutputs) else outputs.claim
    return f"signed {what} of {outputs.ree_digest}\n  {outputs.path}"


def loaded(outputs: LoadReeBundleOutputs) -> str:
    bundle = outputs.loaded
    state = f"sealed {bundle.ree_digest}" if bundle.sealed else "a draft"
    source = "source restored" if bundle.source_restored else "no source"
    return (
        f"loaded {bundle.name} from {outputs.archive_name}: {state}\n"
        f"  {source}, {bundle.overlay_files} script files, {bundle.artifact_files} artifacts"
    )


def verifications(report: SignatureVerifications) -> str:
    subject = f"review {report.review_id} of {report.ree_digest}" if report.review_id else report.ree_digest
    lines = [f"signatures of {subject}"]
    for item in report.signatures:
        signer = f"  {item.signer.identity} ({item.signer.issuer})" if item.signer else ""
        logged = f", logged {item.logged_at}" if item.logged_at else ""
        lines.append(f"  {item.outcome:<14} {item.path}{signer}{logged}")
        if item.reason:
            lines.append(f"  {'':<14} {item.reason}")
    return "\n".join(lines)


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _count(quantity: int) -> str:
    return f"{quantity}x " if quantity != 1 else ""


def _size(size: int) -> str:
    for unit, scale in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if size >= scale:
            return f"{size / scale:.1f} {unit}"
    return f"{size} bytes"


def _took(receipt: ReceiptEnvelope | None) -> str:
    return f" in {receipt.duration_ms / 1000:.1f}s" if receipt is not None else ""


def outputs(value: Any, indent: int = 0) -> str:
    """Any result's outputs as indented ``key: value`` lines."""
    return "\n".join(_lines(value, indent))


def _lines(value: Any, indent: int) -> list[str]:
    pad = "  " * indent
    if isinstance(value, Mapping):
        lines = []
        for key, item in value.items():
            if _scalar(item):
                lines.append(f"{pad}{key}: {_word(item)}")
            elif not item:
                lines.append(f"{pad}{key}: none")
            else:
                lines += [f"{pad}{key}:", *_lines(item, indent + 1)]
        return lines
    if isinstance(value, Sequence) and not isinstance(value, str):
        lines = []
        for item in value:
            if _scalar(item):
                lines.append(f"{pad}- {_word(item)}")
            else:
                inner = _lines(item, indent + 1)
                lines += [f"{pad}- {inner[0].lstrip()}", *inner[1:]] if inner else [f"{pad}-"]
        return lines
    return [f"{pad}{_word(value)}"]


def _scalar(value: Any) -> bool:
    return not isinstance(value, Mapping | list | tuple)


def _word(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)
