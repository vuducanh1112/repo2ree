"""Rule-level fixtures: what each contract rule does and does not say.

The finding code is the shared vocabulary of the rule, the API, and the editor
that renders it, so these are assertions about which code a script earns —
never about the wording of its message.
"""

from __future__ import annotations

import pytest

from repo2ree_core.author_recipes.lint import lint_script
from repo2ree_core.author_recipes.lint.catalog import catalog_codes
from repo2ree_core.author_recipes.lint.lint import CONTRACT_ONLY
from repo2ree_core.author_recipes.lint.models import LintReport, ScriptDeclarations
from repo2ree_core.author_recipes.lint.rules import RULES
from repo2ree_core.author_recipes.targets import ScriptTarget
from repo2ree_protocol.command import TargetKind


def _lint(
    source: str,
    *,
    kind: TargetKind = "experiment_run",
    declarations: ScriptDeclarations | None = None,
) -> LintReport:
    # Contract tier only: these are assertions about the rules, not about which
    # analyzers happen to be installed where the suite runs.
    return lint_script(
        ScriptTarget(kind=kind, path="ree-scripts/experiments/e.sh"),
        source,
        declarations=declarations,
        tiers=CONTRACT_ONLY,
    )


def _codes(report: LintReport) -> set[str]:
    return {finding.code for finding in report.findings}


# ================================================
# Registry
# ================================================


def test_every_registered_rule_declares_only_catalogued_codes() -> None:
    # The registry asserts this at import time; this pins that it stays true,
    # so a rule cannot start emitting a code nothing defines the meaning of.
    known = catalog_codes()
    for rule in RULES:
        assert rule.codes <= known


# ================================================
# Placeholders
# ================================================


def test_unedited_placeholder_is_reported_per_line() -> None:
    report = _lint("EXPECTED='EDIT-ME 0.95'\nEPSILON='EDIT-ME 0.001'\n", kind="experiment_verify")
    findings = [f for f in report.findings if f.code == "unedited_placeholder"]
    assert [f.line for f in findings] == [1, 2]
    assert findings[0].detail == "EXPECTED='EDIT-ME 0.95'"


def test_an_edited_template_earns_no_placeholder_finding() -> None:
    report = _lint("EXPECTED='0.95'\n", kind="experiment_verify")
    assert "unedited_placeholder" not in _codes(report)


# ================================================
# The empty command scaffold
# ================================================


def test_the_unconfigured_scaffold_is_reported() -> None:
    report = _lint('set -eu\nset --\n\nif [ "$#" -eq 0 ]; then exit 64; fi\n')
    findings = [f for f in report.findings if f.code == "empty_command_scaffold"]
    assert [f.line for f in findings] == [2]


def test_a_configured_scaffold_is_not_reported() -> None:
    report = _lint("set -eu\nset -- python main.py\n")
    assert "empty_command_scaffold" not in _codes(report)


def test_the_commented_examples_above_the_scaffold_are_not_the_scaffold() -> None:
    # The renderer writes detected candidates as commented `set --` examples
    # directly above the live line. A text scan would read those as configured.
    report = _lint("#   set -- python main.py\nset -- python other.py\n")
    assert "empty_command_scaffold" not in _codes(report)


def test_a_verify_script_is_never_asked_about_a_scaffold() -> None:
    report = _lint("set --\n", kind="experiment_verify")
    assert "empty_command_scaffold" not in _codes(report)


# ================================================
# Pipelines that mask a failing run
# ================================================


def test_a_piped_run_command_is_reported() -> None:
    report = _lint('docker run img python main.py | tee "result.txt"\n')
    findings = [f for f in report.findings if f.code == "exit_status_masked_by_pipe"]
    assert [f.line for f in findings] == [1]


def test_a_redirected_run_command_is_not() -> None:
    report = _lint('docker run img python main.py > "results/run.log"\n')
    assert "exit_status_masked_by_pipe" not in _codes(report)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param('echo "a | b"\n', id="inside a quoted string"),
        pytest.param("# docker run img | tee x\n", id="inside a comment"),
        pytest.param("command_a || command_b\n", id="an or, not a pipeline"),
    ],
)
def test_what_only_looks_like_a_pipeline_is_not_one(source: str) -> None:
    assert "exit_status_masked_by_pipe" not in _codes(_lint(source))


def test_a_verify_script_may_pipe_freely() -> None:
    # A verify script's exit code is its verdict, and piping is how checks are
    # ordinarily written there (`grep -c ... | ...`).
    report = _lint("grep -o x f | head -n 1\n", kind="experiment_verify")
    assert "exit_status_masked_by_pipe" not in _codes(report)


# ================================================
# Referencing the declared runtime
# ================================================


def test_a_script_that_never_names_the_declared_runtime_is_reported() -> None:
    report = _lint("docker run img python main.py\n", declarations=ScriptDeclarations(runtime_path="runtime.tar"))
    findings = [f for f in report.findings if f.code == "runtime_not_referenced"]
    assert len(findings) == 1
    assert findings[0].detail == "runtime.tar"


def test_naming_the_runtime_once_in_an_assignment_is_enough() -> None:
    # The templates name the path once and use the variable thereafter, which is
    # the whole reason this rule is a mention check and not a dataflow claim.
    source = 'RUNTIME_ARTIFACT="runtime.tar"\ndocker load --input "$RUNTIME_ARTIFACT"\n'
    report = _lint(source, declarations=ScriptDeclarations(runtime_path="runtime.tar"))
    assert "runtime_not_referenced" not in _codes(report)


def test_no_declared_runtime_means_nothing_to_say_about_one() -> None:
    report = _lint("docker run img\n", declarations=ScriptDeclarations(runtime_path=None))
    assert "runtime_not_referenced" not in _codes(report)


def test_no_declarations_at_all_mean_nothing_to_say_about_one() -> None:
    report = _lint("docker run img\n", declarations=None)
    assert "runtime_not_referenced" not in _codes(report)


def test_a_verify_script_is_not_expected_to_touch_the_runtime() -> None:
    report = _lint(
        "grep -Fq x result.txt\n",
        kind="experiment_verify",
        declarations=ScriptDeclarations(runtime_path="runtime.tar"),
    )
    assert "runtime_not_referenced" not in _codes(report)
