"""Shared pieces of the fail-closed activation / experiment scaffolds.

Activation and experiment run scripts share a shape: an empty ``set --`` the
author must fill with the command, a guard that exits 64 if it is still empty,
and — when the runtime image declared any — the detected candidates rendered as
*commented* ``set --`` examples (suggestions, never selected). Centralizing the
shape here keeps the four renderers to just their runtime-load/run plumbing.

``set --`` is a transparent, quoting-safe argv form: it needs no ``eval``, does
no accidental word-splitting, and assumes no shell in the runtime image.
"""

from __future__ import annotations

from repo2ree_core.author_recipes.inference.models import (
    ArgvCommandCandidate,
    ScriptCommandCandidate,
    ShellCommandCandidate,
)
from repo2ree_core.author_recipes.inference.renderers._common import sh_comment, sh_quote
from repo2ree_core.reserved_paths import experiment_slug

EXIT_UNCONFIGURED = 64


def experiment_log_path(experiment_name: str) -> str:
    """The reserved run-log path an experiment scaffold writes and cats."""
    return f"results/{experiment_slug(experiment_name)}.log"


def candidate_examples_block(candidates: list[ScriptCommandCandidate], *, noun: str) -> str:
    """Commented ``set --`` examples for the detected candidates, or a note that
    none were found. ``noun`` is the bare runnable kind ('activation' /
    'experiment'); it reads directly after 'the', so it carries no article."""
    if not candidates:
        return (
            f"# No command was detected in the runtime, so none is suggested. Define the {noun} command\n"
            "# on the 'set --' line below."
        )
    lines = ["# Detected candidate command(s) from the runtime image (review before using):"]
    lines.extend(f"#   {_example(candidate)}" for candidate in candidates)
    lines.append("#")
    lines.append(f"# They stay commented because a runtime's own command is not necessarily the {noun} command.")
    return "\n".join(lines)


def _example(candidate: ScriptCommandCandidate) -> str:
    if isinstance(candidate, ArgvCommandCandidate):
        argv = " ".join(sh_quote(part) for part in candidate.argv)
        return f"set -- {argv}"
    if isinstance(candidate, ShellCommandCandidate):
        return f"set -- {candidate.shell} -c {sh_quote(candidate.command)}"
    return "set --"


def unconfigured_guard(noun: str, edit_hint: str) -> str:
    """The 'command not configured -> exit 64' guard shared by every scaffold."""
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
