"""Stable metadata for repo2ree-owned finding codes.

Only syntax failures block. ShellCheck findings retain their own namespace and
remain advisory because their vocabulary and policy are external.
"""

from __future__ import annotations

from repo2ree_core.author_recipes.lint.models import Finding, FindingSeverity, FindingTier

_CATALOG: dict[str, tuple[FindingTier, FindingSeverity, bool, str]] = {
    "shell_syntax_error": (
        "syntax",
        "error",
        True,
        "The script is not valid POSIX shell, so it cannot run.",
    ),
    "unedited_placeholder": (
        "contract",
        "warning",
        False,
        "An EDIT-ME placeholder from the starter template is still in place, so the claim it "
        "stands for has not been written yet.",
    ),
    "empty_command_scaffold": (
        "contract",
        "warning",
        False,
        "The generated scaffold's 'set --' is still empty, so this script exits 64 instead of running anything.",
    ),
    "runtime_not_referenced": (
        "contract",
        "warning",
        False,
        "The runtime artifact path declared on the REE does not appear anywhere in this script, "
        "so this script may not use the runtime the REE ships.",
    ),
    "exit_status_masked_by_pipe": (
        "contract",
        "warning",
        False,
        "The command is piped, so the exit status reported is the last stage's and a failing run "
        "can be recorded as a pass. Redirect to a file instead.",
    ),
}


def make_finding(
    code: str,
    *,
    path: str,
    line: int | None = None,
    column: int | None = None,
    detail: str | None = None,
) -> Finding:
    """Build a finding, raising ``KeyError`` for an unknown code."""
    tier, severity, blocking, message = _CATALOG[code]
    return Finding(
        code=code,
        tier=tier,
        severity=severity,
        blocking=blocking,
        message=message,
        path=path,
        line=line,
        column=column,
        detail=detail,
    )


def is_known_code(code: str) -> bool:
    return code in _CATALOG


def catalog_codes() -> frozenset[str]:
    return frozenset(_CATALOG)
