from __future__ import annotations

from repo2ree_core.author_recipes.inference.renderers._common import sh_comment, sh_quote
from repo2ree_protocol.inference import ArgvCommandCandidate, ScriptCommandCandidate, ShellCommandCandidate
from repo2ree_ree.reserved_paths import experiment_slug

EXIT_UNCONFIGURED = 64


def experiment_log_path(experiment_name: str) -> str:
    return f"results/{experiment_slug(experiment_name)}.log"


def candidate_examples_block(candidates: list[ScriptCommandCandidate], *, noun: str) -> str:
    if not candidates:
        return (
            "# No command was detected in the experiment environment, so none is suggested.\n"
            f"# Define the {noun} command\n"
            "# on the 'set --' line below."
        )
    lines = ["# Detected candidate command(s) from the experiment environment image (review before using):"]
    lines.extend(f"#   {_example(candidate)}" for candidate in candidates)
    lines.append("#")
    lines.append(
        f"# They stay commented because an experiment environment's own command is not necessarily the {noun} command."
    )
    return "\n".join(lines)


def _example(candidate: ScriptCommandCandidate) -> str:
    if isinstance(candidate, ArgvCommandCandidate):
        argv = " ".join(sh_quote(part) for part in candidate.argv)
        return f"set -- {argv}"
    if isinstance(candidate, ShellCommandCandidate):
        return f"set -- {candidate.shell} -c {sh_quote(candidate.command)}"
    return "set --"


def unconfigured_guard(noun: str, edit_hint: str) -> str:
    return (
        'if [ "$#" -eq 0 ]; then\n'
        f'    echo "{noun} command is not configured." >&2\n'
        f'    echo "{edit_hint}" >&2\n'
        f"    exit {EXIT_UNCONFIGURED}\n"
        "fi"
    )


__all__ = [
    "EXIT_UNCONFIGURED",
    "candidate_examples_block",
    "experiment_log_path",
    "sh_comment",
    "sh_quote",
    "unconfigured_guard",
]
