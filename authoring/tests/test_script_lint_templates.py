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
        ("launch_slurm.sh", "launch"),
        ("launch_direct.sh", "launch"),
        ("check_working_environment.sh", "check_working_environment"),
        ("verify_none.sh", "experiment_verify"),
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
    assert set(_lint_template(name, "experiment_verify")) <= {"unedited_placeholder"}


def test_a_fresh_ree_starts_with_scripts_that_need_no_container_engine() -> None:
    assert "docker" not in reserved_script_template(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
    assert "docker" not in reserved_script_template(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT)


def test_every_template_is_covered_by_a_case_above() -> None:
    covered = {
        "build_experiment_environment_docker.sh",
        "activate_experiment_environment_docker.sh",
        "build_experiment_environment_venv.sh",
        "activate_experiment_environment_venv.sh",
        "experiment_run.sh",
        "launch_slurm.sh",
        "launch_direct.sh",
        "check_working_environment.sh",
        "verify_none.sh",
        "verify_stdout_contains.sh",
        "verify_stdout_regex.sh",
        "verify_numeric_tolerance.sh",
        "verify_file_sha256.sh",
    }
    assert {path.name for path in _TEMPLATES.glob("*.sh")} == covered


def test_the_teed_run_script_the_tutorial_teaches_is_reported() -> None:
    source = 'docker run --rm img python main.py | tee "result.txt"\n'
    report = lint_script(
        ScriptTarget(kind="experiment_run", path="ree-scripts/experiments/e.sh"),
        source,
        tiers=CONTRACT_ONLY,
    )
    assert "exit_status_masked_by_pipe" in {finding.code for finding in report.findings}
    assert report.ok


@pytest.mark.parametrize(
    ("source", "codes"),
    [
        ("exec srun -N1 ${REE_LAUNCH_OPTIONS:-} true\n", {"launch_command_dropped"}),
        ('exec srun -N1 "$@"\n', {"launch_options_ignored"}),
        ('exec sbatch ${REE_LAUNCH_OPTIONS:-} --wrap "$*" "$@"\n', {"launch_does_not_wait"}),
    ],
)
def test_a_launch_that_drops_waits_for_or_closes_off_its_command_is_reported(source: str, codes: set[str]) -> None:
    report = lint_script(ScriptTarget(kind="launch", path="ree-scripts/launch.sh"), source, tiers=CONTRACT_ONLY)
    assert {finding.code for finding in report.findings} == codes


def test_the_check_template_passes_as_shipped_and_each_check_fails_with_what_is_missing(tmp_path: Path) -> None:
    import subprocess

    template = (_TEMPLATES / "check_working_environment.sh").read_text()
    shipped = subprocess.run(["sh", "-c", template], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert shipped.returncode == 0, shipped.stderr
    missing = template.replace(
        "# command -v git >/dev/null 2>&1", "command -v no-such-tool-repo2ree >/dev/null 2>&1"
    ).replace('fail "git is not installed"', 'fail "no-such-tool-repo2ree is not installed"')
    failed = subprocess.run(["sh", "-c", missing], cwd=tmp_path, capture_output=True, text=True, check=False)
    assert failed.returncode == 1
    assert "no-such-tool-repo2ree is not installed" in failed.stderr
