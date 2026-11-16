"""``ree templates`` and ``ree lint-draft``: what an author is offered."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner, Result

from repo2ree_cli.cli import cli
from repo2ree_protocol.catalog import ScriptTemplateCatalog
from repo2ree_protocol.lint import LintReport
from repo2ree_protocol.result import ActionResult

runner = CliRunner()


def ree(tmp_path: Path, *words: str, input: str | None = None) -> Result:  # noqa: A002 — CliRunner's name
    return runner.invoke(cli, ["-C", str(tmp_path), *words], input=input)


def draft(tmp_path: Path, source: str, *words: str) -> LintReport:
    words = words or ("experiment_run", "--experiment-name", "figure-3")
    result = runner.invoke(cli, ["-C", str(tmp_path), "--json", "lint-draft", *words], input=source)
    assert result.exit_code == 0, result.output
    return LintReport.model_validate(ActionResult.model_validate_json(result.stdout).outputs)


def test_templates_prints_the_catalog(tmp_path: Path) -> None:
    result = ree(tmp_path, "--json", "templates")

    assert result.exit_code == 0, result.output
    catalog = ScriptTemplateCatalog.model_validate(ActionResult.model_validate_json(result.stdout).outputs)
    assert catalog.build_experiment_environment.templates[0].is_default


def test_a_person_reads_the_templates_by_where_each_belongs(tmp_path: Path) -> None:
    result = ree(tmp_path, "templates")

    assert result.exit_code == 0, result.output
    assert "ree-scripts/build_experiment_environment.sh" in result.stdout.splitlines()


def test_a_draft_is_checked_against_its_reserved_path(tmp_path: Path) -> None:
    report = draft(tmp_path, 'docker run img main.py | tee "out"\n')

    assert report.target.path == "ree-scripts/experiments/figure-3.sh"
    assert "exit_status_masked_by_pipe" in {finding.code for finding in report.findings}


def test_a_draft_runs_only_the_contract_tier(tmp_path: Path) -> None:
    assert [tier.tier for tier in draft(tmp_path, "set -eu\n").tiers] == ["contract"]


def test_a_draft_is_graded_against_the_declarations_given(tmp_path: Path) -> None:
    report = draft(
        tmp_path,
        "docker run img main.py\n",
        "activate_experiment_environment",
        "--experiment-environment-path",
        "runtime.tar",
    )

    assert "experiment_environment_not_referenced" in {finding.code for finding in report.findings}


def test_a_draft_with_no_declarations_makes_no_claims_about_them(tmp_path: Path) -> None:
    report = draft(tmp_path, "docker run img main.py\n", "activate_experiment_environment")

    assert "experiment_environment_not_referenced" not in {finding.code for finding in report.findings}


def test_lint_never_refuses_a_script_it_dislikes(tmp_path: Path) -> None:
    report = draft(tmp_path, 'set --\nrun | tee "x"\n')

    assert len(report.findings) >= 2
    assert all(finding.blocking is False for finding in report.findings)


def test_an_experiment_draft_without_a_name_is_refused(tmp_path: Path) -> None:
    result = ree(tmp_path, "lint-draft", "experiment_run", input="set -eu\n")

    assert result.exit_code == 2
    assert "requires an experiment_name" in result.stderr


def test_the_draft_check_reads_no_ree(tmp_path: Path) -> None:
    # Nothing at -C is an REE: the check needs only the kind and the source.
    draft(tmp_path, "set -eu\n")

    assert not any(tmp_path.iterdir())
