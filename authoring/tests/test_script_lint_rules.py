from __future__ import annotations

import pytest

from repo2ree_authoring.lint import lint_script
from repo2ree_authoring.lint.catalog import catalog_codes
from repo2ree_authoring.lint.lint import CONTRACT_ONLY
from repo2ree_authoring.lint.rules import RULES
from repo2ree_protocol.command import ScriptTarget, TargetKind
from repo2ree_protocol.lint import LintReport, ScriptDeclarations


def _lint(
    source: str,
    *,
    kind: TargetKind = "experiment_run",
    declarations: ScriptDeclarations | None = None,
) -> LintReport:
    return lint_script(
        ScriptTarget(kind=kind, path="ree-scripts/experiments/e.sh"),
        source,
        declarations=declarations,
        tiers=CONTRACT_ONLY,
    )


def _codes(report: LintReport) -> set[str]:
    return {finding.code for finding in report.findings}


def test_every_registered_rule_declares_only_catalogued_codes() -> None:
    known = catalog_codes()
    for rule in RULES:
        assert rule.codes <= known


def test_unedited_placeholder_is_reported_per_line() -> None:
    report = _lint("EXPECTED='EDIT-ME 0.95'\nEPSILON='EDIT-ME 0.001'\n", kind="experiment_verify")
    findings = [f for f in report.findings if f.code == "unedited_placeholder"]
    assert [f.line for f in findings] == [1, 2]
    assert findings[0].detail == "EXPECTED='EDIT-ME 0.95'"


def test_an_edited_template_earns_no_placeholder_finding() -> None:
    report = _lint("EXPECTED='0.95'\n", kind="experiment_verify")
    assert "unedited_placeholder" not in _codes(report)


def test_the_unconfigured_scaffold_is_reported() -> None:
    report = _lint('set -eu\nset --\n\nif [ "$#" -eq 0 ]; then exit 64; fi\n')
    findings = [f for f in report.findings if f.code == "empty_command_scaffold"]
    assert [f.line for f in findings] == [2]


def test_a_configured_scaffold_is_not_reported() -> None:
    report = _lint("set -eu\nset -- python main.py\n")
    assert "empty_command_scaffold" not in _codes(report)


def test_the_commented_examples_above_the_scaffold_are_not_the_scaffold() -> None:
    report = _lint("#   set -- python main.py\nset -- python other.py\n")
    assert "empty_command_scaffold" not in _codes(report)


def test_a_verify_script_is_never_asked_about_a_scaffold() -> None:
    report = _lint("set --\n", kind="experiment_verify")
    assert "empty_command_scaffold" not in _codes(report)


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
    report = _lint("grep -o x f | head -n 1\n", kind="experiment_verify")
    assert "exit_status_masked_by_pipe" not in _codes(report)


def test_a_script_that_never_names_the_declared_experiment_environment_is_reported() -> None:
    report = _lint(
        "docker run img python main.py\n",
        kind="build_experiment_environment",
        declarations=ScriptDeclarations(experiment_environment_path="runtime.tar"),
    )
    findings = [f for f in report.findings if f.code == "experiment_environment_not_referenced"]
    assert len(findings) == 1
    assert findings[0].detail == "runtime.tar"


def test_naming_the_experiment_environment_once_in_an_assignment_is_enough() -> None:
    source = 'EXPERIMENT_ENVIRONMENT_ARTIFACT="runtime.tar"\ndocker load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"\n'
    report = _lint(source, declarations=ScriptDeclarations(experiment_environment_path="runtime.tar"))
    assert "experiment_environment_not_referenced" not in _codes(report)


def test_no_declared_experiment_environment_means_nothing_to_say_about_one() -> None:
    report = _lint("docker run img\n", declarations=ScriptDeclarations(experiment_environment_path=None))
    assert "experiment_environment_not_referenced" not in _codes(report)


def test_no_declarations_at_all_mean_nothing_to_say_about_one() -> None:
    report = _lint("docker run img\n", declarations=None)
    assert "experiment_environment_not_referenced" not in _codes(report)


def test_a_verify_script_is_not_expected_to_touch_the_experiment_environment() -> None:
    report = _lint(
        "grep -Fq x result.txt\n",
        kind="experiment_verify",
        declarations=ScriptDeclarations(experiment_environment_path="runtime.tar"),
    )
    assert "experiment_environment_not_referenced" not in _codes(report)


def test_a_command_run_inside_the_activation_need_not_name_the_experiment_environment() -> None:
    report = _lint("python main.py\n", declarations=ScriptDeclarations(experiment_environment_path="runtime.tar"))

    assert "experiment_environment_not_referenced" not in {f.code for f in report.findings}
