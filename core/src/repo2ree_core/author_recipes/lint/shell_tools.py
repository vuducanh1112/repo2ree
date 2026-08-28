"""Run optional, bounded shell analyzers over source supplied on stdin."""

from __future__ import annotations

import subprocess

from repo2ree_core.author_recipes.lint.catalog import make_finding
from repo2ree_core.author_recipes.lint.models import Finding, FindingTier, TierStatus
from repo2ree_core.author_recipes.lint.shellcheck_json import parse_json1
from repo2ree_core.tooling import find_tool

_TIMEOUT_SECONDS = 5.0

_DIALECT = "sh"


def run_syntax_check(
    source: str, *, path: str, timeout: float = _TIMEOUT_SECONDS
) -> tuple[TierStatus, tuple[Finding, ...]]:
    """Parse source with the host's POSIX shell without executing it."""
    shell = find_tool("sh")
    if shell is None:
        return _unavailable("syntax", "no POSIX shell is available to parse the script"), ()

    completed = _run([shell, "-n"], source, timeout)
    if completed is None:
        return _unavailable("syntax", "the shell did not answer within the timeout"), ()

    status = TierStatus(tier="syntax", status="ran", tool=shell)
    if completed.returncode == 0:
        return status, ()
    detail = completed.stderr.strip() or None
    return status, (make_finding("shell_syntax_error", path=path, line=_line_from(detail), detail=detail),)


def run_shellcheck(
    source: str, *, path: str, timeout: float = _TIMEOUT_SECONDS
) -> tuple[TierStatus, tuple[Finding, ...]]:
    """Lint the script with ShellCheck, in the same dialect the bench runs it in."""
    shellcheck = find_tool("shellcheck")
    if shellcheck is None:
        return _unavailable("shell", "shellcheck is not installed on this bench"), ()

    completed = _run([shellcheck, "--shell", _DIALECT, "--format=json1", "-"], source, timeout)
    if completed is None:
        return _unavailable("shell", "shellcheck did not answer within the timeout"), ()

    version = _version(shellcheck, timeout)
    status = TierStatus(tier="shell", status="ran", tool=shellcheck, tool_version=version)
    return status, parse_json1(completed.stdout, path=path)


def _run(argv: list[str], stdin: str, timeout: float) -> subprocess.CompletedProcess[str] | None:
    """The tool's result, or None when it could not be run at all."""
    try:
        return subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _version(shellcheck: str, timeout: float) -> str | None:
    completed = _run([shellcheck, "--version"], "", timeout)
    if completed is None:
        return None
    for line in completed.stdout.splitlines():
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip()
    return None


def _line_from(message: str | None) -> int | None:
    """Extract a line number from a shell diagnostic when one is present."""
    if not message:
        return None
    for token in message.replace(":", " ").split():
        if token.isdigit():
            return int(token)
    return None


def _unavailable(tier: FindingTier, detail: str) -> TierStatus:
    return TierStatus(tier=tier, status="unavailable", detail=detail)
