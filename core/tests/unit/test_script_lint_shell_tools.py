"""The shell tier: what happens when the analyzers are there, and when they are not.

The tools are optional by design, so the absence cases matter as much as the
present ones — a bench without ShellCheck must lint on the other tiers and say
that it did, never fail or silently report nothing found.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from repo2ree_core.author_recipes.lint import lint_script, shell_tools
from repo2ree_core.author_recipes.lint.models import Finding, LintReport, TierStatus
from repo2ree_core.author_recipes.lint.shell_tools import run_shellcheck, run_syntax_check
from repo2ree_core.author_recipes.targets import ScriptTarget

ShellRunner = Callable[..., tuple[TierStatus, tuple[Finding, ...]]]


def _tier(report: LintReport, tier: str) -> TierStatus:
    return next(status for status in report.tiers if status.tier == tier)


def test_a_valid_script_earns_no_syntax_finding() -> None:
    status, findings = run_syntax_check("set -eu\necho hi\n", path="x.sh")
    assert status.status == "ran"
    assert findings == ()


def test_an_unparseable_script_is_the_one_blocking_finding() -> None:
    status, (finding,) = run_syntax_check("if true; then\n", path="x.sh")
    assert status.status == "ran"
    assert finding.code == "shell_syntax_error"
    assert finding.blocking is True
    # The shell's own message is the only place a reader learns where it gave up.
    assert finding.detail


@pytest.mark.parametrize("runner", [run_syntax_check, run_shellcheck])
def test_a_missing_tool_is_reported_as_unavailable_not_as_clean(
    runner: ShellRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(shell_tools, "find_tool", lambda _name: None)
    status, findings = runner("set -eu\n", path="x.sh")
    assert status.status == "unavailable"
    assert status.detail
    assert findings == ()


def test_a_tool_that_cannot_be_executed_is_unavailable_rather_than_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shell_tools, "find_tool", lambda _name: "/nonexistent/shellcheck")
    status, findings = run_shellcheck("set -eu\n", path="x.sh")
    assert status.status == "unavailable"
    assert findings == ()


def test_asking_for_no_tool_tiers_runs_neither(monkeypatch: pytest.MonkeyPatch) -> None:
    # The contract tier is pure Python; the other two spawn a process. A caller
    # that cannot spawn one asks for the contract tier alone and still gets a report.
    def _fail(*_: object, **__: object) -> None:
        raise AssertionError("no process may be spawned for the contract tier")

    monkeypatch.setattr(shell_tools, "_run", _fail)
    report = lint_script(
        ScriptTarget(kind="build", path="ree-scripts/build_script.sh"),
        "set -eu\n",
        tiers=frozenset({"contract"}),
    )
    assert [status.tier for status in report.tiers] == ["contract"]


def test_a_full_run_records_every_tier_it_attempted() -> None:
    report = lint_script(ScriptTarget(kind="build", path="b.sh"), "set -eu\necho hi\n")
    assert {status.tier for status in report.tiers} == {"syntax", "shell", "contract"}
    # The contract rules need no tool, so that tier can never be unavailable.
    assert _tier(report, "contract").status == "ran"
