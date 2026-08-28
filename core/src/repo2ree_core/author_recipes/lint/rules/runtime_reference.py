"""Check whether run and build scripts mention the declared runtime path."""

from __future__ import annotations

from typing import ClassVar

from repo2ree_core.author_recipes.lint.catalog import make_finding
from repo2ree_core.author_recipes.lint.models import Finding, ScriptContext
from repo2ree_protocol.command import TargetKind


class RuntimeReferenceRule:
    code = "runtime_not_referenced"
    codes: ClassVar[frozenset[str]] = frozenset({"runtime_not_referenced"})
    applies_to: ClassVar[frozenset[TargetKind]] = frozenset({"build", "activation_run", "experiment_run"})

    def check(self, context: ScriptContext) -> tuple[Finding, ...]:
        declared = context.declarations.runtime_path
        if not declared:
            return ()
        if context.words.mentions(declared) is not None:
            return ()
        return (make_finding(self.code, path=context.path, detail=declared),)
