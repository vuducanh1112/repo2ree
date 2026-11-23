from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.inference.models import BindingKind, CheckResult, DecisionContext
from repo2ree_core.author_recipes.inference.warnings import make_warning
from repo2ree_core.digests import short_hash
from repo2ree_protocol.inference import (
    ArgvCommandCandidate,
    CommandCandidatesBinding,
    CommandCandidatesObservation,
    ImageCommandBinding,
    InferenceWarning,
    ScriptCommandCandidate,
    ShellCommandCandidate,
)

_LONG_RUNNING_HINTS = ("serve", "server", "runserver", "gunicorn", "uvicorn", "daemon", "http.server")


class DockerConfigCommandsCheck:
    code = "docker_config_commands"
    label = "Does the experiment environment image declare a command?"
    branches = frozenset({"candidates", "none"})
    requires: frozenset[BindingKind] = frozenset({"experiment_environment_contract"})
    produces: ClassVar[dict[str, frozenset[BindingKind]]] = {
        "candidates": frozenset({"command_candidates"}),
        "none": frozenset({"command_candidates"}),
    }

    def evaluate(self, context: DecisionContext) -> CheckResult:
        candidates, warnings = _candidates_from_binding(context.binding("image_command"))

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


def _candidates_from_binding(
    binding: object,
) -> tuple[list[ScriptCommandCandidate], list[InferenceWarning]]:
    if not isinstance(binding, ImageCommandBinding):
        return [], []

    candidates: list[ScriptCommandCandidate] = []
    warnings: list[InferenceWarning] = []
    if binding.argv:
        text = " ".join(binding.argv)
        candidates.append(
            ArgvCommandCandidate(
                candidate_id=_candidate_id("argv", text),
                argv=binding.argv,
                source="docker_config",
            )
        )
        if _looks_long_running(text):
            warnings.append(make_warning("possibly_long_running"))
    elif binding.shell_command:
        candidates.append(
            ShellCommandCandidate(
                candidate_id=_candidate_id("shell", binding.shell_command),
                command=binding.shell_command,
                source="docker_config",
            )
        )
        warnings.append(make_warning("shell_required_in_experiment_environment"))
        if _looks_long_running(binding.shell_command):
            warnings.append(make_warning("possibly_long_running"))
    return candidates, warnings


def _looks_long_running(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _LONG_RUNNING_HINTS)


def _candidate_id(kind: str, text: str) -> str:
    return f"{kind}:{short_hash(text.encode())}"
