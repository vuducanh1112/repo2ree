"""What a person reads: each result ``ree`` prints, as plain lines.

``--json`` prints the same results as data; nothing here is read by a machine.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from typing import Any

from repo2ree_protocol.audit import ReeAudit, StepAudit
from repo2ree_protocol.catalog import ReeStepKey, ReeSteps, ScriptTemplateCatalog
from repo2ree_protocol.document import ReeStatusReport, WorkbenchReeDocument
from repo2ree_protocol.history import OperationHistory
from repo2ree_protocol.inference import InferenceReport, TargetInferenceResult
from repo2ree_ree.review import ReviewRecord, ReviewSet

_MARKS = {"complete": "✓", "ready": "·", "blocked": "✗"}
_EVIDENCE = {"current": "current", "stale": "STALE", "missing": "missing", "not_applicable": "n/a"}

# What to run for each step, as a person types it.
HINTS: dict[ReeStepKey, str] = {
    "source": "ree acquire-source --archive PATH, or ree acquire-source --origin-url URL",
    "metadata": "ree define --name NAME --version VERSION --description TEXT",
    "hbom": "ree hbom",
    "check_working_environment": "ree edit check_working_environment, then ree check-working-environment",
    "evaluate": "ree evaluate",
    "build_experiment_environment": (
        "ree define --artifact-path PATH, ree infer --target build_experiment_environment --write, "
        "then ree build-experiment-environment"
    ),
    "sbom": "ree sbom",
    "crosscheck": "ree sbom-check",
    "activation": "ree infer --target activate_experiment_environment --write, then ree test-activation",
    "experiments": (
        "ree edit experiment_run:NAME, ree define --experiment NAME --output PATH, then ree experiment NAME"
    ),
    "seal": "ree seal",
}


def next_hint(steps: ReeSteps) -> str | None:
    """The line that says what to do next, or None when every step is complete."""
    following = next((step for step in steps.steps if step.key == steps.next), None)
    if following is None:
        return None
    return f"next: {following.label}: {HINTS[following.key]}"


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
    lines += ["", next_hint(report.steps) or "every step is complete"]
    return "\n".join(lines)


def _step_evidence(audit: ReeAudit) -> dict[ReeStepKey, StepAudit]:
    return {
        "source": audit.source,
        "evaluate": audit.evaluation,
        "check_working_environment": audit.working_environment_check,
        "build_experiment_environment": audit.experiment_environment,
        "sbom": audit.sbom,
        "crosscheck": audit.sbom_cross_check,
        "activation": audit.activation,
    }


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
    source = receipts.source
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
        ("source", doc.audit.source),
        ("evaluation", doc.audit.evaluation),
        ("hardware", doc.audit.hardware),
        ("working environment check", doc.audit.working_environment_check),
        ("experiment environment", doc.audit.experiment_environment),
        ("sbom", doc.audit.sbom),
        ("sbom cross-check", doc.audit.sbom_cross_check),
        ("activation", doc.audit.activation),
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
        (catalog.check_working_environment.path, catalog.check_working_environment.templates),
        (catalog.launch.path, catalog.launch.templates),
        (catalog.build_experiment_environment.path, catalog.build_experiment_environment.templates),
        (catalog.activate_experiment_environment.path, catalog.activate_experiment_environment.templates),
        (catalog.experiment.run_script_path_pattern, catalog.experiment.templates),
        (catalog.experiment.verify_script_path_pattern, catalog.verify),
    )
    lines = []
    for path, entries in sections:
        lines.append(path)
        lines += [f"  {entry.key:<24} {entry.label}{'  (default)' if entry.is_default else ''}" for entry in entries]
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
