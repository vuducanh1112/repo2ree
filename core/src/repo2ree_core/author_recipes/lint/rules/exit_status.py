"""Report pipelines that can hide the run command's exit status."""

from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.lint.catalog import make_finding
from repo2ree_core.author_recipes.lint.models import Finding, ScriptContext
from repo2ree_protocol.command import TargetKind


class PipeMaskingRule:
    code = "exit_status_masked_by_pipe"
    codes: ClassVar[frozenset[str]] = frozenset({"exit_status_masked_by_pipe"})
    applies_to: ClassVar[frozenset[TargetKind]] = frozenset({"build", "activation_run", "experiment_run"})

    def check(self, context: ScriptContext) -> tuple[Finding, ...]:
        return tuple(make_finding(self.code, path=context.path, line=word.line) for word in context.words.operator("|"))
