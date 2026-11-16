"""Tests for the baked-in bundle reproducer (``run.sh`` + ``REPRODUCING.md``)."""

import os
import subprocess
import tarfile
from pathlib import Path
from typing import Any

from repo2ree_core.persistence.layout import (
    ACQUIRE_SCRIPT_FILENAME,
    ARTIFACTS_DIRNAME,
    BUNDLE_ACQUIRE_ENTRY_PATH,
    BUNDLE_MATERIALIZE_ENTRY_PATH,
    BUNDLE_REPRODUCER_README_ENTRY_PATH,
    BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH,
    MATERIALIZE_SCRIPT_FILENAME,
    OVERLAY_DIRNAME,
    SNAPSHOT_FILENAME,
    WORKSPACE_DIRNAME,
)
from repo2ree_core.reproduction.acquire_source import build_acquire_sh
from repo2ree_core.reproduction.commands import REPRODUCTION_COMMANDS
from repo2ree_core.reproduction.materialize_workspace import build_materialize_sh
from repo2ree_core.reproduction.reproducer import (
    build_reproducer_sh,
    reproducer_entries,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
    RESERVED_LAUNCH_SCRIPT,
)


def test_reproducer_entries_are_run_sh_scripts_and_readme():
    entries = dict(reproducer_entries())
    assert set(entries) == {
        BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH,
        BUNDLE_ACQUIRE_ENTRY_PATH,
        BUNDLE_MATERIALIZE_ENTRY_PATH,
        BUNDLE_REPRODUCER_README_ENTRY_PATH,
    }
    assert BUNDLE_REPRODUCER_SCRIPT_ENTRY_PATH == "run.sh"
    assert f"ree/{ACQUIRE_SCRIPT_FILENAME}" == BUNDLE_ACQUIRE_ENTRY_PATH
    assert f"ree/{MATERIALIZE_SCRIPT_FILENAME}" == BUNDLE_MATERIALIZE_ENTRY_PATH
    assert entries["run.sh"].startswith(b"#!/bin/sh")
    # run.sh delegates acquisition and the clear-and-merge to the bundled scripts.
    assert ACQUIRE_SCRIPT_FILENAME.encode() in entries["run.sh"]
    assert MATERIALIZE_SCRIPT_FILENAME.encode() in entries["run.sh"]
    assert entries[BUNDLE_ACQUIRE_ENTRY_PATH].startswith(b"#!/bin/sh")
    assert entries[BUNDLE_MATERIALIZE_ENTRY_PATH].startswith(b"#!/bin/sh")
    assert b"@@" not in entries["run.sh"]
    assert b"@@" not in entries[BUNDLE_REPRODUCER_README_ENTRY_PATH]
    # Defaults fall back to the reserved script paths.
    assert RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT.encode() in entries["run.sh"]
    assert RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT.encode() in entries["run.sh"]


def test_the_readme_points_at_the_check_of_what_the_scripts_need():
    def readme(check: str | None) -> str:
        return dict(reproducer_entries(check_script=check))["REPRODUCING.md"].decode()

    assert "left no check" in readme(None)
    text = readme(RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT)
    assert f"`{RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT}`" in text
    assert "sh run.sh check-working-environment" in text
    assert "@@" not in text


def test_reproducer_sh_is_deterministic_for_equal_inputs():
    kwargs: dict[str, Any] = {
        "build_experiment_environment_script": RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
        "activate_experiment_environment_script": RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
        "experiments": [("exp one", "ree-scripts/experiments/exp one.sh", "")],
        "experiment_environment_workspace_path": "runtime.tar.gz",
        "experiment_environment_artifact_basename": "runtime.tar.gz",
    }
    assert build_reproducer_sh(**kwargs) == build_reproducer_sh(**kwargs)


def test_generated_run_sh_passes_shellcheck_or_sh_n():
    """The generated script must at least parse as POSIX sh."""
    script = build_reproducer_sh(
        build_experiment_environment_script=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
        activate_experiment_environment_script=RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
        experiments=[
            ("demo exp", "ree-scripts/experiments/demo exp.sh", "ree-scripts/experiments/demo exp.verify.sh"),
            ("two", "ree-scripts/experiments/two.sh", ""),
        ],
        experiment_environment_workspace_path="runtime.tar.gz",
        experiment_environment_artifact_basename="runtime.tar.gz",
    ).decode("utf-8")
    result = subprocess.run(["sh", "-n", "/dev/stdin"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def _seed_extracted_bundle(
    tmp_path: Path,
    *,
    include_experiment_environment: bool,
    experiments: list[tuple[str, str, str]],
    launch: str | None = None,
    check: str | None = None,
) -> Path:
    """Lay out an extracted-bundle tree (run.sh + ree/...) without sealing."""
    root = tmp_path / "download"
    ree = root / "ree"
    (ree / OVERLAY_DIRNAME / "ree-scripts" / "experiments").mkdir(parents=True)
    (ree / ARTIFACTS_DIRNAME).mkdir(parents=True)
    # An extracted bundle need not contain this directory: run.sh creates and
    # materializes it. Seed it here so individual reproducer commands can be
    # exercised against an already-extracted working tree.
    (ree / WORKSPACE_DIRNAME).mkdir(parents=True)

    # snapshot.tar.gz with a single source file at top level
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("hello\n")
    with tarfile.open(ree / SNAPSHOT_FILENAME, "w:gz") as tar:
        tar.add(src / "hello.txt", arcname="hello.txt")

    overlay = ree / OVERLAY_DIRNAME / "ree-scripts"
    (overlay / "build_experiment_environment.sh").write_text("#!/bin/sh\necho BUILT > runtime.tar.gz\necho did-build\n")
    # The activation reads the experiment environment it enters, so a test of it alone shows which one that was.
    (overlay / "activate_experiment_environment.sh").write_text('#!/bin/sh\ncat runtime.tar.gz\nexec "$@"\n')
    for name, script, verify in experiments:
        # The run script materializes its stdout to a workspace file so a verify
        # script can read it back — there is no injected stdout variable.
        (ree / OVERLAY_DIRNAME / script).write_text(f"#!/bin/sh\necho exp:{name} | tee run.log\n")
        if verify:
            (ree / OVERLAY_DIRNAME / verify).write_text(f'#!/bin/sh\ngrep -q "exp:{name}" run.log\n')

    if include_experiment_environment:
        (ree / ARTIFACTS_DIRNAME / "runtime.tar.gz").write_text("SEALED-EXPERIMENT_ENVIRONMENT\n")

    run_sh = build_reproducer_sh(
        build_experiment_environment_script=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
        activate_experiment_environment_script=RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
        experiments=experiments,
        experiment_environment_workspace_path="runtime.tar.gz",
        experiment_environment_artifact_basename="runtime.tar.gz" if include_experiment_environment else None,
        launch_script=RESERVED_LAUNCH_SCRIPT if launch is not None else None,
        check_script=RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT if check is not None else None,
    )
    if check is not None:
        (ree / OVERLAY_DIRNAME / RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT).write_text(check)
    if launch is not None:
        (ree / OVERLAY_DIRNAME / RESERVED_LAUNCH_SCRIPT).write_text(launch)
    (root / "run.sh").write_bytes(run_sh)
    # run.sh delegates acquisition to this bundled script (no origin baked in,
    # so it extracts the snapshot) and the clear-and-merge to the materialize script.
    (ree / ACQUIRE_SCRIPT_FILENAME).write_bytes(build_acquire_sh())
    (ree / MATERIALIZE_SCRIPT_FILENAME).write_bytes(build_materialize_sh())
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", "run.sh", *args], cwd=root, text=True, capture_output=True)


def test_run_sh_materializes_and_reuses_sealed_experiment_environment(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo exp", "ree-scripts/experiments/demo exp.sh", "ree-scripts/experiments/demo exp.verify.sh")],
    )

    listed = _run(root)
    assert listed.returncode == 0, listed.stderr
    assert "demo exp" in listed.stdout
    # Materialization patched the overlay scripts into the workspace.
    assert (root / "ree" / WORKSPACE_DIRNAME / "ree-scripts" / "build_experiment_environment.sh").is_file()
    assert (root / "ree" / WORKSPACE_DIRNAME / "hello.txt").is_file()

    activated = _run(root, "test-activation")
    assert activated.returncode == 0, activated.stderr
    assert "Reusing sealed experiment environment" in activated.stdout
    assert "did-build" not in activated.stdout  # build skipped
    assert "SEALED-EXPERIMENT_ENVIRONMENT" in activated.stdout  # activation read the reused experiment environment
    assert "$ sh ree-scripts/activate_experiment_environment.sh true" in activated.stdout  # and ran alone

    exp = _run(root, "experiment", "demo exp")
    assert exp.returncode == 0, exp.stderr
    assert "exp:demo exp" in exp.stdout
    # The bundled verify script read the materialized stdout and passed.
    assert "VERIFIED: pass" in exp.stdout


def test_run_sh_experiment_verify_failure_fails_the_command(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")],
    )
    (root / "ree" / OVERLAY_DIRNAME / "ree-scripts" / "experiments" / "demo.verify.sh").write_text(
        "#!/bin/sh\ngrep -q NOT-THE-CLAIMED-RESULT run.log\n"
    )
    result = _run(root, "experiment", "demo")
    assert result.returncode != 0
    assert "VERIFIED: fail" in result.stdout


def test_run_sh_verify_reads_workspace_with_no_injected_env(tmp_path):
    """The verify script reads outputs straight from the workspace; nothing is injected."""
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")],
    )
    (root / "ree" / OVERLAY_DIRNAME / "ree-scripts" / "experiments" / "demo.sh").write_text(
        "#!/bin/sh\necho claimed-result | tee run.log\necho ok > out.txt\n"
    )
    (root / "ree" / OVERLAY_DIRNAME / "ree-scripts" / "experiments" / "demo.verify.sh").write_text(
        "#!/bin/sh\n"
        '[ -z "${R2R_RUN_STDOUT:-}" ] || exit 1\n'  # no injected stream variables
        "grep -q claimed-result run.log || exit 1\n"
        "grep -q ok out.txt || exit 1\n"
    )
    result = _run(root, "experiment", "demo")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "VERIFIED: pass" in result.stdout


def test_run_sh_test_activation_fails_when_the_activation_does_not_hand_over(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=True, experiments=[])
    (root / "ree" / OVERLAY_DIRNAME / "ree-scripts" / "activate_experiment_environment.sh").write_text(
        "#!/bin/sh\nexit 3\n"
    )
    result = _run(root, "test-activation")
    assert result.returncode != 0


def test_run_sh_verify_only_rechecks_prior_run_without_rerunning(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")],
    )
    # Produce the outputs once.
    first = _run(root, "experiment", "demo")
    assert first.returncode == 0, first.stderr
    assert "VERIFIED: pass" in first.stdout

    # Verify-only re-checks the retained outputs without invoking the run script.
    again = _run(root, "verify", "demo")
    assert again.returncode == 0, again.stderr + again.stdout
    assert "== verify: demo ==" in again.stdout
    assert "VERIFIED: pass" in again.stdout
    assert "$ sh ree-scripts/experiments/demo.sh" not in again.stdout  # run script not re-run
    assert "exp:demo" not in again.stdout  # no fresh run output


def test_run_sh_verify_only_fails_when_outputs_absent(tmp_path):
    # No prior run, so the materialized workspace has no run.log for the verify
    # script to read — verifying without producing the outputs first fails.
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")],
    )
    result = _run(root, "verify", "demo")
    assert result.returncode != 0
    assert "VERIFIED: fail" in result.stdout


def test_run_sh_verify_only_needs_an_experiment(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=True, experiments=[])
    result = _run(root, "verify")
    assert result.returncode != 0
    assert "usage:" in result.stderr


def test_run_sh_verify_only_errors_when_no_verify_script_declared(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "")],
    )
    result = _run(root, "verify", "demo")
    assert result.returncode != 0
    assert "no verify script" in (result.stderr + result.stdout)


def test_run_sh_verify_only_errors_for_unknown_experiment(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")],
    )
    result = _run(root, "verify", "nope")
    assert result.returncode != 0
    assert "no experiment named" in (result.stderr + result.stdout)


def test_run_sh_all_runs_full_pipeline_end_to_end(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[
            ("demo exp", "ree-scripts/experiments/demo exp.sh", "ree-scripts/experiments/demo exp.verify.sh"),
            ("two", "ree-scripts/experiments/two.sh", ""),
        ],
    )
    result = _run(root, "all")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # Whole pipeline, in order: materialize -> experiment environment reuse -> activation -> every experiment.
    assert "Reusing sealed experiment environment" in out
    assert "did-build" not in out  # reused, not rebuilt
    order = [out.index(m) for m in ("== test-activation ==", "exp:demo exp", "exp:two", "All steps completed.")]
    assert order == sorted(order)
    # The verified experiment reported its verdict inside the pipeline.
    assert "VERIFIED: pass" in out


def test_run_sh_all_builds_once_then_runs_experiments(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path, include_experiment_environment=False, experiments=[("a", "ree-scripts/experiments/a.sh", "")]
    )
    result = _run(root, "all")
    assert result.returncode == 0, result.stderr
    # No sealed experiment environment -> build exactly once, ahead of activation and the experiment.
    assert result.stdout.count("did-build") == 1
    assert "exp:a" in result.stdout


def test_run_sh_all_aborts_on_failing_experiment(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[
            ("boom", "ree-scripts/experiments/boom.sh", ""),
            ("after", "ree-scripts/experiments/after.sh", ""),
        ],
    )
    (root / "ree" / OVERLAY_DIRNAME / "ree-scripts" / "experiments" / "boom.sh").write_text("#!/bin/sh\nexit 3\n")
    result = _run(root, "all")
    assert result.returncode != 0
    assert "exp:after" not in result.stdout  # stopped at the failing step
    assert "All steps completed." not in result.stdout


def test_run_sh_builds_when_no_sealed_experiment_environment(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=False, experiments=[])
    activated = _run(root, "test-activation")
    assert activated.returncode == 0, activated.stderr
    assert "did-build" in activated.stdout  # fell back to building
    assert "BUILT" in activated.stdout  # activation read the freshly built experiment environment


def test_run_sh_rejects_unknown_command_and_missing_experiment(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=True, experiments=[])
    assert _run(root, "bogus").returncode != 0
    missing = _run(root, "experiment", "nope")
    assert missing.returncode != 0
    assert "no experiment named" in missing.stderr


def test_run_sh_exposes_every_reproduction_command(tmp_path):
    """Every shared reproduction verb is a real dispatch arm — the --help mirror."""
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=True, experiments=[])
    for command in REPRODUCTION_COMMANDS:
        # experiment needs a name; the rest are bare verbs that must succeed.
        if command.name == "experiment":
            continue
        result = _run(root, command.name)
        assert result.returncode == 0, f"{command.name}: {result.stderr}"
    listed = _run(root, "list").stdout
    for command in REPRODUCTION_COMMANDS:
        assert command.name in listed
        assert command.summary in listed


def test_materialize_workspace_resets_stray_state(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=True, experiments=[])
    _run(root)  # initial materialize
    stray = root / "ree" / WORKSPACE_DIRNAME / "stray.txt"
    stray.write_text("left over from a previous run\n")

    result = _run(root, "materialize-workspace")
    assert result.returncode == 0, result.stderr
    assert not stray.exists()  # clean slate
    assert (root / "ree" / WORKSPACE_DIRNAME / "hello.txt").is_file()  # source restored
    assert (
        root / "ree" / WORKSPACE_DIRNAME / "ree-scripts" / "build_experiment_environment.sh"
    ).is_file()  # overlay restored


def test_acquire_source_warns_when_no_snapshot_and_no_origin(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=False, experiments=[])
    (root / "ree" / SNAPSHOT_FILENAME).unlink()  # sourceless, and no origin baked in

    result = _run(root, "acquire-source")
    assert result.returncode == 0, result.stderr
    assert "overlay-only" in result.stdout


def test_run_sh_runs_the_experiment_inside_the_activation_and_verifies_outside_it(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_experiment_environment=True,
        experiments=[("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")],
    )
    scripts = root / "ree" / OVERLAY_DIRNAME / "ree-scripts"
    (scripts / "activate_experiment_environment.sh").write_text(
        '#!/bin/sh\nACTIVATED=inside\nexport ACTIVATED\nexec "$@"\n'
    )
    (scripts / "experiments" / "demo.sh").write_text('#!/bin/sh\necho "$ACTIVATED" > run.log\n')
    (scripts / "experiments" / "demo.verify.sh").write_text(
        '#!/bin/sh\ngrep -qx inside run.log && [ -z "${ACTIVATED:-}" ]\n'
    )

    result = _run(root, "experiment", "demo")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERIFIED: pass" in result.stdout


# A launch script that logs each command it launches, with the options it was given, then runs it.
_LOGGING_LAUNCH = '#!/bin/sh\nprintf "%s|%s\\n" "${REE_LAUNCH_OPTIONS:-}" "$*" >> launched.log\nexec "$@"\n'
_DEMO = [("demo", "ree-scripts/experiments/demo.sh", "ree-scripts/experiments/demo.verify.sh")]


def _launched(root: Path) -> list[str]:
    log = root / "ree" / WORKSPACE_DIRNAME / "launched.log"
    return log.read_text().splitlines() if log.is_file() else []


def _run_with(root: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", "run.sh", *args], cwd=root, text=True, capture_output=True, env={**os.environ, **env})


def test_run_sh_launches_every_script_through_the_authors_launch(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path, include_experiment_environment=False, experiments=_DEMO, launch=_LOGGING_LAUNCH
    )
    result = _run(root, "all")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _launched(root) == [
        "|sh ree-scripts/build_experiment_environment.sh",
        "|sh ree-scripts/activate_experiment_environment.sh true",
        "|sh ree-scripts/activate_experiment_environment.sh sh ree-scripts/experiments/demo.sh",
        "|sh ree-scripts/experiments/demo.verify.sh",
    ]
    assert f"$ sh {RESERVED_LAUNCH_SCRIPT} sh ree-scripts/experiments/demo.verify.sh" in result.stdout
    assert f"$ sh {RESERVED_LAUNCH_SCRIPT} sh {RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT} true" in result.stdout


def test_run_sh_hands_a_reproducers_options_to_the_authors_launch(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path, include_experiment_environment=True, experiments=_DEMO, launch=_LOGGING_LAUNCH
    )
    result = _run_with(root, {"REE_LAUNCH_OPTIONS": "--partition=short"}, "experiment", "demo")
    assert result.returncode == 0, result.stdout + result.stderr
    assert {line.split("|")[0] for line in _launched(root)} == {"--partition=short"}


def test_run_sh_runs_directly_when_the_reproducer_asks_for_native(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path, include_experiment_environment=True, experiments=_DEMO, launch=_LOGGING_LAUNCH
    )
    result = _run_with(root, {"REE_LAUNCH": "native"}, "all")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _launched(root) == []
    assert "$ sh ree-scripts/activate_experiment_environment.sh true" in result.stdout


def test_run_sh_launches_with_the_reproducers_own_command(tmp_path):
    # An REE without a launch runs directly unless the reproducer names a launcher of their own.
    root = _seed_extracted_bundle(tmp_path, include_experiment_environment=True, experiments=_DEMO)
    scripts = root / "ree" / OVERLAY_DIRNAME / "ree-scripts"
    (scripts / "experiments" / "demo.sh").write_text('#!/bin/sh\necho "exp:demo ${LAUNCHED_BY:-directly}" > run.log\n')
    direct = _run(root, "experiment", "demo")
    assert direct.returncode == 0, direct.stdout + direct.stderr
    assert (root / "ree" / WORKSPACE_DIRNAME / "run.log").read_text() == "exp:demo directly\n"
    mine = _run_with(root, {"REE_LAUNCH": "env LAUNCHED_BY=mine"}, "experiment", "demo")
    assert mine.returncode == 0, mine.stdout + mine.stderr
    assert (root / "ree" / WORKSPACE_DIRNAME / "run.log").read_text() == "exp:demo mine\n"
    assert "$ env LAUNCHED_BY=mine sh ree-scripts/activate_experiment_environment.sh sh" in mine.stdout


def test_the_readme_says_how_the_scripts_were_launched_and_how_to_launch_them_otherwise():
    launched = dict(reproducer_entries(launch_script=RESERVED_LAUNCH_SCRIPT))[BUNDLE_REPRODUCER_README_ENTRY_PATH]
    assert f"`{RESERVED_LAUNCH_SCRIPT}`".encode() in launched
    assert b"REE_LAUNCH=native" in launched
    assert b"REE_LAUNCH_OPTIONS=" in launched
    direct = dict(reproducer_entries())[BUNDLE_REPRODUCER_README_ENTRY_PATH]
    assert b"The author ran every script directly" in direct


def test_run_sh_all_runs_the_authors_check_before_anything_else_and_stops_when_it_fails(tmp_path):
    passing = _seed_extracted_bundle(
        tmp_path / "passing", include_experiment_environment=False, experiments=_DEMO, check="echo checked-here\n"
    )
    result = _run(passing, "all")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.index("checked-here") < result.stdout.index("did-build")

    failing = _seed_extracted_bundle(
        tmp_path / "failing",
        include_experiment_environment=False,
        experiments=_DEMO,
        check="echo no gpu here >&2\nexit 1\n",
    )
    result = _run(failing, "all")
    assert result.returncode != 0
    assert "no gpu here" in result.stderr
    assert "did-build" not in result.stdout


def test_run_sh_checks_the_working_environment_on_its_own(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path, include_experiment_environment=False, experiments=_DEMO, check="echo checked-here\n"
    )
    assert "checked-here" in _run(root, "check-working-environment").stdout

    unchecked = _seed_extracted_bundle(tmp_path / "unchecked", include_experiment_environment=False, experiments=_DEMO)
    result = _run(unchecked, "check-working-environment")
    assert result.returncode == 0
    assert "declared no check" in result.stdout
