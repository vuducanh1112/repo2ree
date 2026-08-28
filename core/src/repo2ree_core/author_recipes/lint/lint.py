"""Compose syntax, ShellCheck, and repo2ree contract checks for one script."""

from __future__ import annotations

from repo2ree_core.author_recipes.lint.models import (
    Finding,
    FindingTier,
    LintReport,
    ScriptContext,
    ScriptDeclarations,
    TierStatus,
)
from repo2ree_core.author_recipes.lint.rules import RULES
from repo2ree_core.author_recipes.lint.shell_tools import run_shellcheck, run_syntax_check
from repo2ree_core.author_recipes.lint.shellwords import tokenize
from repo2ree_core.author_recipes.targets import ScriptTarget

ENGINE_VERSION = "1"

ALL_TIERS: frozenset[FindingTier] = frozenset({"syntax", "shell", "contract"})
CONTRACT_ONLY: frozenset[FindingTier] = frozenset({"contract"})


def lint_script(
    target: ScriptTarget,
    source: str,
    *,
    declarations: ScriptDeclarations | None = None,
    tiers: frozenset[FindingTier] = ALL_TIERS,
) -> LintReport:
    """Everything the requested tiers observe about one script."""
    findings: list[Finding] = []
    statuses: list[TierStatus] = []

    if "syntax" in tiers:
        status, produced = run_syntax_check(source, path=target.path)
        statuses.append(status)
        findings.extend(produced)

    if "shell" in tiers:
        status, produced = run_shellcheck(source, path=target.path)
        statuses.append(status)
        findings.extend(produced)

    if "contract" in tiers:
        context = ScriptContext(
            target=target,
            source=source,
            words=tokenize(source),
            declarations=declarations or ScriptDeclarations(),
        )
        for rule in RULES:
            if target.kind in rule.applies_to:
                findings.extend(rule.check(context))
        statuses.append(TierStatus(tier="contract", status="ran"))

    return LintReport(
        engine_version=ENGINE_VERSION,
        target=target,
        findings=tuple(sorted(findings, key=lambda f: (f.line or 0, f.code, f.detail or ""))),
        tiers=tuple(statuses),
    )
