"""Contract-rule registry with import-time catalog validation."""

from __future__ import annotations

from typing import ClassVar, Protocol

from repo2ree_core.author_recipes.lint.catalog import catalog_codes
from repo2ree_core.author_recipes.lint.models import Finding, ScriptContext
from repo2ree_core.author_recipes.lint.rules.exit_status import PipeMaskingRule
from repo2ree_core.author_recipes.lint.rules.placeholders import (
    EmptyCommandScaffoldRule,
    UneditedPlaceholderRule,
)
from repo2ree_core.author_recipes.lint.rules.runtime_reference import RuntimeReferenceRule
from repo2ree_protocol.command import TargetKind


class LintRule(Protocol):
    """What every contract rule exposes."""

    codes: ClassVar[frozenset[str]]
    applies_to: ClassVar[frozenset[TargetKind]]

    def check(self, context: ScriptContext) -> tuple[Finding, ...]: ...


RULES: tuple[LintRule, ...] = (
    UneditedPlaceholderRule(),
    EmptyCommandScaffoldRule(),
    PipeMaskingRule(),
    RuntimeReferenceRule(),
)


def _validate_rules() -> None:
    known = catalog_codes()
    for rule in RULES:
        unknown = rule.codes - known
        if unknown:
            raise ValueError(f"{type(rule).__name__} declares uncatalogued codes: {sorted(unknown)}")


_validate_rules()

__all__ = ["RULES", "LintRule"]
