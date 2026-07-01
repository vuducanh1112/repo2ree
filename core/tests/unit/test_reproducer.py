"""Tests for the baked-in bundle reproducer (``run.sh`` + ``REPRODUCING.md``)."""

import subprocess
import tarfile
from pathlib import Path

from repo2ree_core.ree_scripts.acquire_source import build_acquire_sh
from repo2ree_core.ree_scripts.materialize_workspace import build_materialize_sh
from repo2ree_core.ree_scripts.reproducer import (
    REPRODUCER_ACQUIRE_ENTRY_PATH,
    REPRODUCER_MATERIALIZE_ENTRY_PATH,
    REPRODUCER_README_ENTRY_PATH,
    REPRODUCER_SCRIPT_ENTRY_PATH,
    build_reproducer_sh,
    reproducer_entries,
    runtime_artifact_basename_from_remap,
)
from repo2ree_core.reproduction import REPRODUCTION_COMMANDS
from repo2ree_core.reserved_paths import RESERVED_ACTIVATION_SCRIPT, RESERVED_BUILD_SCRIPT
from repo2ree_core.storage.layout import (
    ACQUIRE_SCRIPT_FILENAME,
    ARTIFACTS_DIRNAME,
    MATERIALIZE_SCRIPT_FILENAME,
    OVERLAY_DIRNAME,
    SNAPSHOT_FILENAME,
    WORKSPACE_DIRNAME,
)


def test_reproducer_entries_are_run_sh_scripts_and_readme():
    entries = dict(reproducer_entries())
    assert set(entries) == {
        REPRODUCER_SCRIPT_ENTRY_PATH,
        REPRODUCER_ACQUIRE_ENTRY_PATH,
        REPRODUCER_MATERIALIZE_ENTRY_PATH,
        REPRODUCER_README_ENTRY_PATH,
    }
    assert REPRODUCER_SCRIPT_ENTRY_PATH == "run.sh"
    assert REPRODUCER_ACQUIRE_ENTRY_PATH == f"ree/{ACQUIRE_SCRIPT_FILENAME}"
    assert REPRODUCER_MATERIALIZE_ENTRY_PATH == f"ree/{MATERIALIZE_SCRIPT_FILENAME}"
    assert entries["run.sh"].startswith(b"#!/bin/sh")
    # run.sh delegates acquisition and the clear-and-merge to the bundled scripts.
    assert ACQUIRE_SCRIPT_FILENAME.encode() in entries["run.sh"]
    assert MATERIALIZE_SCRIPT_FILENAME.encode() in entries["run.sh"]
    assert entries[REPRODUCER_ACQUIRE_ENTRY_PATH].startswith(b"#!/bin/sh")
    assert entries[REPRODUCER_MATERIALIZE_ENTRY_PATH].startswith(b"#!/bin/sh")
    assert b"@@" not in entries["run.sh"]
    assert b"@@" not in entries[REPRODUCER_README_ENTRY_PATH]
    # Defaults fall back to the reserved script paths.
    assert RESERVED_BUILD_SCRIPT.encode() in entries["run.sh"]
    assert RESERVED_ACTIVATION_SCRIPT.encode() in entries["run.sh"]


def test_reproducer_sh_is_deterministic_for_equal_inputs():
    kwargs = dict(
        build_script=RESERVED_BUILD_SCRIPT,
        activation_script=RESERVED_ACTIVATION_SCRIPT,
        experiments=[("exp one", "ree/experiments/exp one.sh")],
        runtime_workspace_path="runtime.tar.gz",
        runtime_artifact_basename="runtime.tar.gz",
    )
    assert build_reproducer_sh(**kwargs) == build_reproducer_sh(**kwargs)


def test_runtime_artifact_basename_from_remap():
    remap = {"build/runtime.tar.gz": "artifacts/runtime.tar.gz"}
    assert runtime_artifact_basename_from_remap("build/runtime.tar.gz", remap) == "runtime.tar.gz"
    # Not in remap (runtime not sealed in) or missing path -> None (rebuild path).
    assert runtime_artifact_basename_from_remap("build/runtime.tar.gz", {}) is None
    assert runtime_artifact_basename_from_remap(None, remap) is None
    assert runtime_artifact_basename_from_remap("build/runtime.tar.gz", "not-a-dict") is None


def test_generated_run_sh_passes_shellcheck_or_sh_n():
    """The generated script must at least parse as POSIX sh."""
    script = build_reproducer_sh(
        build_script=RESERVED_BUILD_SCRIPT,
        activation_script=RESERVED_ACTIVATION_SCRIPT,
        experiments=[("demo exp", "ree/experiments/demo exp.sh"), ("two", "ree/experiments/two.sh")],
        runtime_workspace_path="runtime.tar.gz",
        runtime_artifact_basename="runtime.tar.gz",
    ).decode("utf-8")
    result = subprocess.run(["sh", "-n", "/dev/stdin"], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def _seed_extracted_bundle(
    tmp_path: Path,
    *,
    include_runtime: bool,
    experiments: list[tuple[str, str]],
) -> Path:
    """Lay out an extracted-bundle tree (run.sh + ree/...) without sealing."""
    root = tmp_path / "download"
    ree = root / "ree"
    (ree / OVERLAY_DIRNAME / "ree" / "experiments").mkdir(parents=True)
    (ree / ARTIFACTS_DIRNAME).mkdir(parents=True)
    (ree / WORKSPACE_DIRNAME).mkdir(parents=True)  # the empty placeholder the bundle ships

    # snapshot.tar.gz with a single source file at top level
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("hello\n")
    with tarfile.open(ree / SNAPSHOT_FILENAME, "w:gz") as tar:
        tar.add(src / "hello.txt", arcname="hello.txt")

    overlay = ree / OVERLAY_DIRNAME / "ree"
    (overlay / "build_script.sh").write_text("#!/bin/sh\necho BUILT > runtime.tar.gz\necho did-build\n")
    (overlay / "activation.sh").write_text("#!/bin/sh\ncat runtime.tar.gz\n")
    for name, script in experiments:
        (ree / OVERLAY_DIRNAME / script).write_text(f"#!/bin/sh\necho exp:{name}\n")

    if include_runtime:
        (ree / ARTIFACTS_DIRNAME / "runtime.tar.gz").write_text("SEALED-RUNTIME\n")

    run_sh = build_reproducer_sh(
        build_script=RESERVED_BUILD_SCRIPT,
        activation_script=RESERVED_ACTIVATION_SCRIPT,
        experiments=experiments,
        runtime_workspace_path="runtime.tar.gz",
        runtime_artifact_basename="runtime.tar.gz" if include_runtime else None,
    )
    (root / "run.sh").write_bytes(run_sh)
    # run.sh delegates acquisition to this bundled script (no origin baked in,
    # so it extracts the snapshot) and the clear-and-merge to the materialize script.
    (ree / ACQUIRE_SCRIPT_FILENAME).write_bytes(build_acquire_sh())
    (ree / MATERIALIZE_SCRIPT_FILENAME).write_bytes(build_materialize_sh())
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", "run.sh", *args], cwd=root, text=True, capture_output=True)


def test_run_sh_materializes_and_reuses_sealed_runtime(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path, include_runtime=True, experiments=[("demo exp", "ree/experiments/demo exp.sh")]
    )

    listed = _run(root)
    assert listed.returncode == 0, listed.stderr
    assert "demo exp" in listed.stdout
    # Materialization patched the overlay scripts into the workspace.
    assert (root / "ree" / WORKSPACE_DIRNAME / "ree" / "build_script.sh").is_file()
    assert (root / "ree" / WORKSPACE_DIRNAME / "hello.txt").is_file()

    activated = _run(root, "test-activation")
    assert activated.returncode == 0, activated.stderr
    assert "Reusing sealed runtime" in activated.stdout
    assert "did-build" not in activated.stdout  # build skipped
    assert "SEALED-RUNTIME" in activated.stdout  # activation read the reused runtime

    exp = _run(root, "experiment", "demo exp")
    assert exp.returncode == 0, exp.stderr
    assert "exp:demo exp" in exp.stdout


def test_run_sh_all_runs_full_pipeline_end_to_end(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_runtime=True,
        experiments=[("demo exp", "ree/experiments/demo exp.sh"), ("two", "ree/experiments/two.sh")],
    )
    result = _run(root, "all")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    # Whole pipeline, in order: materialize -> runtime reuse -> activation -> every experiment.
    assert "Reusing sealed runtime" in out
    assert "did-build" not in out  # reused, not rebuilt
    order = [out.index(m) for m in ("== test-activation ==", "exp:demo exp", "exp:two", "All steps completed.")]
    assert order == sorted(order)


def test_run_sh_all_builds_once_then_runs_experiments(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_runtime=False, experiments=[("a", "ree/experiments/a.sh")])
    result = _run(root, "all")
    assert result.returncode == 0, result.stderr
    # No sealed runtime -> build exactly once, ahead of activation and the experiment.
    assert result.stdout.count("did-build") == 1
    assert "exp:a" in result.stdout


def test_run_sh_all_aborts_on_failing_experiment(tmp_path):
    root = _seed_extracted_bundle(
        tmp_path,
        include_runtime=True,
        experiments=[("boom", "ree/experiments/boom.sh"), ("after", "ree/experiments/after.sh")],
    )
    (root / "ree" / OVERLAY_DIRNAME / "ree" / "experiments" / "boom.sh").write_text("#!/bin/sh\nexit 3\n")
    result = _run(root, "all")
    assert result.returncode != 0
    assert "exp:after" not in result.stdout  # stopped at the failing step
    assert "All steps completed." not in result.stdout


def test_run_sh_builds_when_no_sealed_runtime(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_runtime=False, experiments=[])
    activated = _run(root, "test-activation")
    assert activated.returncode == 0, activated.stderr
    assert "did-build" in activated.stdout  # fell back to building
    assert "BUILT" in activated.stdout  # activation read the freshly built runtime


def test_run_sh_rejects_unknown_command_and_missing_experiment(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_runtime=True, experiments=[])
    assert _run(root, "bogus").returncode != 0
    missing = _run(root, "experiment", "nope")
    assert missing.returncode != 0
    assert "no experiment named" in missing.stderr


def test_run_sh_exposes_every_reproduction_command(tmp_path):
    """Every shared reproduction verb is a real dispatch arm — the --help mirror."""
    root = _seed_extracted_bundle(tmp_path, include_runtime=True, experiments=[])
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
    root = _seed_extracted_bundle(tmp_path, include_runtime=True, experiments=[])
    _run(root)  # initial materialize
    stray = root / "ree" / WORKSPACE_DIRNAME / "stray.txt"
    stray.write_text("left over from a previous run\n")

    result = _run(root, "materialize-workspace")
    assert result.returncode == 0, result.stderr
    assert not stray.exists()  # clean slate
    assert (root / "ree" / WORKSPACE_DIRNAME / "hello.txt").is_file()  # source restored
    assert (root / "ree" / WORKSPACE_DIRNAME / "ree" / "build_script.sh").is_file()  # overlay restored


def test_acquire_source_warns_when_no_snapshot_and_no_origin(tmp_path):
    root = _seed_extracted_bundle(tmp_path, include_runtime=False, experiments=[])
    (root / "ree" / SNAPSHOT_FILENAME).unlink()  # sourceless, and no origin baked in

    result = _run(root, "acquire-source")
    assert result.returncode == 0, result.stderr
    assert "overlay-only" in result.stdout
