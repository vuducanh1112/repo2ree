"""Docker image-config command candidates for the runtime-command fork.

Reads a resolved Docker runtime contract's archive config and offers its
``Entrypoint``/``Cmd`` as *candidate* commands — suggestions the author confirms,
never an automatic selection. Exec-form (JSON) values become argv candidates;
shell-form values are offered verbatim as shell candidates (never rewritten into
guessed argv) and flag that the runtime needs a shell. Plausibly long-running
commands (servers, daemons) are flagged too.

The candidates ride into rendering as commented ``set --`` examples. When the
artifact is absent (a contract established from an unchanged generated build, not
an inspected artifact) or holds no config command, the candidate set is simply
empty and the fail-closed scaffold still renders.
"""

from __future__ import annotations

import hashlib

from repo2ree_core.script_inference.artifact_inspection import (
    DockerArchiveInspection,
    inspect_runtime_artifact,
)
from repo2ree_core.script_inference.models import (
    ArgvCommandCandidate,
    BindingKind,
    CheckResult,
    CommandCandidatesBinding,
    CommandCandidatesObservation,
    DecisionContext,
    DockerRuntimeContract,
    RuntimeContractBinding,
    ScriptCommandCandidate,
    ShellCommandCandidate,
)
from repo2ree_core.script_inference.warnings import make_warning

# Substrings that mark a plausibly persistent command (server / daemon).
_LONG_RUNNING_HINTS = ("serve", "server", "runserver", "gunicorn", "uvicorn", "daemon", "http.server")


def _docker_contract(context: DecisionContext) -> DockerRuntimeContract | None:
    binding = context.binding("runtime_contract")
    if isinstance(binding, RuntimeContractBinding) and isinstance(binding.contract, DockerRuntimeContract):
        return binding.contract
    return None


class DockerConfigCommandsCheck:
    code = "docker_config_commands"
    label = "Does the runtime image declare a command?"
    branches = frozenset({"candidates", "none"})
    requires: frozenset[BindingKind] = frozenset({"runtime_contract"})
    produces: dict[str, frozenset[BindingKind]] = {
        "candidates": frozenset({"command_candidates"}),
        "none": frozenset({"command_candidates"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        contract = _docker_contract(context)
        candidates: list[ScriptCommandCandidate] = []
        warnings = []
        if contract is not None:
            candidates, warnings = _candidates_from_archive(context, contract)

        branch = "candidates" if candidates else "none"
        observed = CommandCandidatesObservation(
            count=len(candidates),
            sources=[c.source for c in candidates],
        )
        return CheckResult(
            branch=branch,
            observed=observed,
            bindings=(CommandCandidatesBinding(candidates=candidates),),
            warnings=warnings,
        )


def _candidates_from_archive(context: DecisionContext, contract: DockerRuntimeContract):
    stream = context.runtime.accessor.open(contract.artifact_path)
    if stream is None:
        return [], []
    try:
        inspection = inspect_runtime_artifact(stream)
    finally:
        stream.close()
    if not isinstance(inspection, DockerArchiveInspection):
        return [], []

    candidates: list[ScriptCommandCandidate] = []
    warnings = []
    if inspection.argv:
        text = " ".join(inspection.argv)
        candidates.append(
            ArgvCommandCandidate(
                candidate_id=_candidate_id("argv", text),
                argv=inspection.argv,
                source="docker_config",
            )
        )
        if _looks_long_running(text):
            warnings.append(make_warning("possibly_long_running"))
    elif inspection.shell_command:
        candidates.append(
            ShellCommandCandidate(
                candidate_id=_candidate_id("shell", inspection.shell_command),
                command=inspection.shell_command,
                source="docker_config",
            )
        )
        warnings.append(make_warning("shell_required_in_runtime"))
        if _looks_long_running(inspection.shell_command):
            warnings.append(make_warning("possibly_long_running"))
    return candidates, warnings


def _looks_long_running(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _LONG_RUNNING_HINTS)


def _candidate_id(kind: str, text: str) -> str:
    return f"{kind}:{hashlib.sha256(text.encode()).hexdigest()[:12]}"
