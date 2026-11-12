"""Every shipped starter template lints clean, and the known-bad shapes do not.

This is the test that keeps the catalog honest. The templates are what repo2ree
hands an author to start from; a rule that fires on one of them is either a bug
in the rule or a bug in the template, and either way somebody has to look. The
counterpart cases below are the documented pitfalls the guides warn about, each
pinned to the code that names it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_authoring.lint import lint_script
from repo2ree_authoring.lint.lint import CONTRACT_ONLY
from repo2ree_authoring.templates import reserved_script_template
from repo2ree_protocol.command import ScriptTarget, TargetKind
from repo2ree_protocol.lint import ScriptDeclarations
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
)

_TEMPLATES = Path(__file__).resolve().parents[2] / "authoring/src/repo2ree_authoring/templates"

# Each template names its experiment environment, so an REE declaring that path is the one it
# is written for. Declaring something else would make every template "wrong" for
# a reason that is about the REE, not about the template.
_DOCKER = ScriptDeclarations(experiment_environment_path="runtime.tar")
_VENV = ScriptDeclarations(experiment_environment_path="runtime-venv.tar.gz")


def _lint_template(name: str, kind: TargetKind) -> tuple[str, ...]:
    source = (_TEMPLATES / name).read_text()
    report = lint_script(
        ScriptTarget(kind=kind, path=f"ree-scripts/{name}"),
        source,
        declarations=_VENV if "venv" in name else _DOCKER,
        tiers=CONTRACT_ONLY,
    )
    return tuple(finding.code for finding in report.findings)


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("build_experiment_environment_docker.sh", "build_experiment_environment"),
        ("activate_experiment_environment_docker.sh", "activate_experiment_environment"),
        ("build_experiment_environment_venv.sh", "build_experiment_environment"),
        ("activate_experiment_environment_venv.sh", "activate_experiment_environment"),
        ("experiment_run.sh", "experiment_run"),
    ],
)
def test_a_run_or_build_template_lints_clean(name: str, kind: TargetKind) -> None:
    assert _lint_template(name, kind) == ()


@pytest.mark.parametrize(
    "name",
    [
        "verify_stdout_contains.sh",
        "verify_stdout_regex.sh",
        "verify_numeric_tolerance.sh",
        "verify_file_sha256.sh",
    ],
)
def test_a_verify_template_says_only_that_it_is_unedited(name: str) -> None:
    # Verify templates ship EDIT-ME on the parts that carry the claim, by
    # design: an unedited one must fail rather than pass vacuously. Saying so is
    # the correct reading, and it must be the *only* thing said.
    assert set(_lint_template(name, "experiment_verify")) <= {"unedited_placeholder"}


def test_a_fresh_ree_starts_with_scripts_that_suit_its_environment() -> None:
    assert "docker build" in reserved_script_template(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, "container")
    assert "docker" not in reserved_script_template(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, "host")
    assert "docker run" in reserved_script_template(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, "container")
    assert "docker" not in reserved_script_template(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, "host")


def test_every_template_is_covered_by_a_case_above() -> None:
    # A new template that nobody linted would quietly escape this file.
    covered = {
        "build_experiment_environment_docker.sh",
        "activate_experiment_environment_docker.sh",
        "build_experiment_environment_venv.sh",
        "activate_experiment_environment_venv.sh",
        "experiment_run.sh",
        "verify_stdout_contains.sh",
        "verify_stdout_regex.sh",
        "verify_numeric_tolerance.sh",
        "verify_file_sha256.sh",
    }
    assert {path.name for path in _TEMPLATES.glob("*.sh")} == covered


# ================================================
# The pitfalls the guides warn about
# ================================================


def test_the_teed_run_script_the_tutorial_teaches_is_reported() -> None:
    # docs/public/how-to/experiments.md names this: a pipeline reports tee's
    # exit status, so a failing run is recorded as a pass.
    source = 'docker run --rm img python main.py | tee "result.txt"\n'
    report = lint_script(
        ScriptTarget(kind="experiment_run", path="ree-scripts/experiments/e.sh"),
        source,
        tiers=CONTRACT_ONLY,
    )
    assert "exit_status_masked_by_pipe" in {finding.code for finding in report.findings}
    # Advisory: the author may have meant it. Lint reports; it does not refuse.
    assert report.ok
