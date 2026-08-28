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

from repo2ree_core.author_recipes.lint import lint_script
from repo2ree_core.author_recipes.lint.lint import CONTRACT_ONLY
from repo2ree_core.author_recipes.lint.models import ScriptDeclarations
from repo2ree_core.author_recipes.targets import ScriptTarget
from repo2ree_protocol.command import TargetKind

_TEMPLATES = Path(__file__).resolve().parents[3] / "core/src/repo2ree_core/author_recipes/templates"

# The templates name `runtime.tar`, so an REE declaring that path is the one
# they are written for. Declaring something else would make every template
# "wrong" for a reason that is about the REE, not about the template.
_DECLARATIONS = ScriptDeclarations(runtime_path="runtime.tar")


def _lint_template(name: str, kind: TargetKind) -> tuple[str, ...]:
    source = (_TEMPLATES / name).read_text()
    report = lint_script(
        ScriptTarget(kind=kind, path=f"ree-scripts/{name}"),
        source,
        declarations=_DECLARATIONS,
        tiers=CONTRACT_ONLY,
    )
    return tuple(finding.code for finding in report.findings)


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("build_script_docker.sh", "build"),
        ("activation_docker.sh", "activation_run"),
        ("experiment_run_docker.sh", "experiment_run"),
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


def test_every_template_is_covered_by_a_case_above() -> None:
    # A new template that nobody linted would quietly escape this file.
    covered = {
        "build_script_docker.sh",
        "activation_docker.sh",
        "experiment_run_docker.sh",
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
