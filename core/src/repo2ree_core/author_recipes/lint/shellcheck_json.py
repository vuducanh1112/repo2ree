"""Map ShellCheck ``json1`` output to advisory findings."""

from __future__ import annotations

import json

from repo2ree_core.author_recipes.lint.models import Finding, FindingSeverity

_LEVELS: dict[str, FindingSeverity] = {
    "error": "error",
    "warning": "warning",
    "info": "info",
    "style": "info",
}


def parse_json1(payload: str, *, path: str) -> tuple[Finding, ...]:
    """Read findings from one ``shellcheck --format=json1`` document."""
    try:
        document = json.loads(payload)
    except json.JSONDecodeError:
        return ()
    if not isinstance(document, dict):
        return ()
    comments = document.get("comments")
    if not isinstance(comments, list):
        return ()

    findings: list[Finding] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        code = comment.get("code")
        message = comment.get("message")
        if code is None or not isinstance(message, str):
            continue
        findings.append(
            Finding(
                code=f"shellcheck:SC{code}",
                tier="shell",
                severity=_LEVELS.get(str(comment.get("level")), "info"),
                blocking=False,
                message=message,
                path=path,
                line=_as_int(comment.get("line")),
                column=_as_int(comment.get("column")),
            )
        )
    return tuple(findings)


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
