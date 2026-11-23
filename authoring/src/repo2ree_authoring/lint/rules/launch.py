from __future__ import annotations

from typing import ClassVar

from repo2ree_authoring.lint.catalog import make_finding
from repo2ree_authoring.lint.models import ScriptContext
from repo2ree_protocol.command import TargetKind
from repo2ree_protocol.lint import Finding

_NOT_WAITING = ("sbatch", "salloc")


class LaunchContractRule:
    codes: ClassVar[frozenset[str]] = frozenset(
        {"launch_command_dropped", "launch_options_ignored", "launch_does_not_wait"}
    )
    applies_to: ClassVar[frozenset[TargetKind]] = frozenset({"launch"})

    def check(self, context: ScriptContext) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        if context.words.mentions("$@") is None:
            findings.append(make_finding("launch_command_dropped", path=context.path))
        if context.words.mentions("REE_LAUNCH_OPTIONS") is None:
            findings.append(make_finding("launch_options_ignored", path=context.path))
        findings.extend(
            make_finding("launch_does_not_wait", path=context.path, line=word.line, detail=word.text)
            for word in context.words.words
            if word.text in _NOT_WAITING
        )
        return tuple(findings)
