"""Docker image-config command candidates for the runtime-command fork.

Turns the image's declared ``Entrypoint``/``Cmd`` — parsed once when the artifact
was inspected and carried here on the ``image_command`` binding — into *candidate*
commands: suggestions the author confirms, never an automatic selection.
Exec-form (JSON) values become argv candidates; shell-form values are offered
verbatim as shell candidates (never rewritten into guessed argv) and flag that
the runtime needs a shell. Plausibly long-running commands (servers, daemons) are
flagged too.

The candidates ride into rendering as commented ``set --`` examples. When no
``image_command`` binding is present (a contract established from an unchanged
generated build, not an inspected artifact) or it declares no command, the
candidate set is simply empty and the fail-closed scaffold still renders. This
check reads only the already-parsed binding — it never re-opens the archive.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.models import (
    ArgvCommandCandidate,
    BindingKind,
    CheckResult,
    CommandCandidatesBinding,
    CommandCandidatesObservation,
    DecisionContext,
    ImageCommandBinding,
    InferenceWarning,
    ScriptCommandCandidate,
    ShellCommandCandidate,
)
from repo2ree_core.authoring.script_inference.warnings import make_warning
from repo2ree_core.digests import short_hash

# Substrings that mark a plausibly persistent command (server / daemon).
_LONG_RUNNING_HINTS = ("serve", "server", "runserver", "gunicorn", "uvicorn", "daemon", "http.server")


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
        warnings.append(make_warning("shell_required_in_runtime"))
        if _looks_long_running(binding.shell_command):
            warnings.append(make_warning("possibly_long_running"))
    return candidates, warnings


def _looks_long_running(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _LONG_RUNNING_HINTS)


def _candidate_id(kind: str, text: str) -> str:
    return f"{kind}:{short_hash(text.encode())}"
