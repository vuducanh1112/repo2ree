"""Static checks over the author's REE-owned shell scripts.

Lint reads a script and says what it notices; it never writes, never refuses,
and never rewrites. Only a script that cannot run at all is reported as
blocking — see ``catalog`` for why everything else is advice.

The sibling of ``templates`` and ``inference``, and the one that arrives last:
those two answer "what should this script say", and this one answers "does what
you wrote agree with what the REE declares".
"""

from __future__ import annotations

from repo2ree_core.author_recipes.lint.lint import (
    ALL_TIERS,
    CONTRACT_ONLY,
    ENGINE_VERSION,
    lint_script,
)
from repo2ree_core.author_recipes.lint.models import (
    Finding,
    FindingSeverity,
    FindingTier,
    LintReport,
    ScriptDeclarations,
    TierStatus,
)

__all__ = [
    "ALL_TIERS",
    "CONTRACT_ONLY",
    "ENGINE_VERSION",
    "Finding",
    "FindingSeverity",
    "FindingTier",
    "LintReport",
    "ScriptDeclarations",
    "TierStatus",
    "lint_script",
]
