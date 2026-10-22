"""Preserved artifacts remain useful after source cleanup."""

import fcntl
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from repo2ree_testbed.artifacts import case_dir, case_key, run_dir
from repo2ree_testbed.preservation import TestRecorder


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO2REE_TEST_RUN_DIR", str(tmp_path / "artifacts"))
    return TestRecorder("core/tests/test_example.py::test_case")


def test_copy_preserves_hidden_git_lfs_pending_and_working_files(tmp_path, recorder):
    source = tmp_path / "ree"
    for relative in [
        "ree.json",
        ".git/HEAD",
        ".git/lfs/objects/ab/cd/payload",
        ".git/repo2ree/operations/pending.json",
        "workspace/output",
    ]:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    (source / "alias").symlink_to("workspace/output")
    recorder.local(source)
    recorder.local(source)
    shutil.rmtree(source)
    recorder.finish("failed")
    document = json.loads((recorder.directory / "manifest.json").read_text())
    assert document["outcome"] == "failed"
    assert len(document["repositories"]) == 1
    saved = recorder.directory / document["repositories"][0]["path"]
    assert (saved / ".git/lfs/objects/ab/cd/payload").read_text() == ".git/lfs/objects/ab/cd/payload"
    assert (saved / "alias").is_symlink()
    assert (saved / "workspace/output").read_text() == "workspace/output"


def test_copy_does_not_follow_external_symlink(tmp_path, recorder):
    source = tmp_path / "ree"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private")
    (source / "link").symlink_to(outside)
    recorder.local(source)
    saved = recorder.directory / str(recorder.repositories[0].path)
    assert (saved / "link").is_symlink()
    assert not (saved / "outside").exists()


def test_removed_source_is_explicitly_unavailable(tmp_path, recorder):
    recorder.local(tmp_path / "missing")
    assert recorder.repositories[0].status == "unavailable"


def test_failed_copy_unpauses_container(recorder, monkeypatch):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        if args[1] == "cp":
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 0, "false\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    recorder.workbench("example")
    assert [args[1] for args in commands] == ["inspect", "pause", "cp", "unpause"]
    assert recorder.repositories[0].status == "error"


def test_existing_pause_is_preserved(recorder, monkeypatch):
    commands = []

    def run(args, **kwargs):
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "true\n", "")

    monkeypatch.setattr(subprocess, "run", run)
    recorder.workbench("example")
    assert [args[1] for args in commands] == ["inspect", "cp"]


def test_case_names_are_safe_and_collision_resistant():
    assert case_key("test[a/b]") != case_key("test[a_b]")
    assert "/" not in case_key("../../test")


def test_run_directory_is_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO2REE_TEST_RUN_DIR", str(tmp_path / "run"))
    assert run_dir() == tmp_path / "run"


def test_discovery_includes_reviews_only_once(tmp_path, recorder):
    root = tmp_path / "source"
    for scope in (root, root / "reviews/reviewer"):
        (scope / ".git").mkdir(parents=True)
        (scope / "ree.json").write_text("{}")
    recorder.discover(root)
    assert len(recorder.repositories) == 1
    saved = recorder.directory / str(recorder.repositories[0].path)
    assert (saved / "reviews/reviewer/.git").is_dir()


def test_saved_repository_remains_usable_after_source_removal(tmp_path, recorder):
    source = tmp_path / "real-ree"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "ree.json").write_text('{"name":"recorded"}')
    subprocess.run(["git", "-C", str(source), "add", "ree.json"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgSign=false",
            "commit",
            "-qm",
            "captured state",
        ],
        check=True,
    )
    recorder.local(source)
    shutil.rmtree(source)
    saved = recorder.directory / str(recorder.repositories[0].path)
    result = subprocess.run(
        ["git", "-C", str(saved), "show", "HEAD:ree.json"], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == {"name": "recorded"}


def test_busy_repository_records_error_without_blocking(tmp_path, recorder):
    root = tmp_path / "busy"
    (root / ".git").mkdir(parents=True)
    with (root / ".git/repo2ree.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        recorder.local(root)
    assert recorder.repositories[0].status == "error"


@pytest.mark.parametrize("failure", ["call", "teardown"])
def test_pytest_retains_evidence_before_cleanup_and_records_failure(tmp_path, failure):
    project = tmp_path / "project"
    project.mkdir()
    artifacts = tmp_path / "recordings"
    (project / "test_example.py").write_text(
        "import shutil\nimport pytest\n"
        "@pytest.fixture\ndef ree(tmp_path, test_recording):\n"
        "    root = tmp_path / 'ree'\n"
        "    (root / '.git').mkdir(parents=True)\n"
        "    (root / 'ree.json').write_text('{}')\n"
        "    yield root\n"
        "    test_recording.local(root)\n"
        "    shutil.rmtree(root)\n"
        + ("    raise RuntimeError('teardown failure')\n" if failure == "teardown" else "")
        + "def test_example(ree):\n"
        + ("    assert False\n" if failure == "call" else "    assert ree.is_dir()\n")
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "repo2ree_testbed.pytest_plugin", "--confcutdir", str(project), "-q"],
        cwd=project,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "REPO2REE_TEST_RUN_DIR": str(artifacts),
            "REPO2REE_ASSURANCE_DIR": str(project / "test-artifacts/assurance"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    (manifest,) = (artifacts / "python/tests").rglob("manifest.json")
    document = json.loads(manifest.read_text())
    assert document["outcome"] == "failed"
    (repository,) = document["repositories"]
    assert repository["status"] == "recorded"
    assert (manifest.parent / repository["path"] / ".git").is_dir()
    assert not Path(repository["source"]).exists()


def test_readable_test_path_and_repeated_execution_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO2REE_TEST_RUN_DIR", str(tmp_path))
    nodeid = "api/tests/integration/test_pipeline.py::test_pipeline"
    expected = tmp_path / "python/tests/api/integration/test_pipeline/test_pipeline"
    assert case_dir(nodeid) == expected
    previous = TestRecorder(nodeid)
    previous.directory.mkdir(parents=True)
    (previous.directory / "stale.ndjson").write_text("old")
    current = TestRecorder(nodeid)
    assert current.directory == expected
    assert not (expected / "stale.ndjson").exists()


def test_assurance_artifacts_have_an_independent_root(tmp_path, monkeypatch):
    monkeypatch.setenv("REPO2REE_ASSURANCE_DIR", str(tmp_path / "test-artifacts/assurance"))
    monkeypatch.setenv("REPO2REE_TEST_RUN_DIR", str(tmp_path))
    assert (
        case_dir("conformance/tests/test_matrix.py::test_rows")
        == tmp_path / "test-artifacts/assurance/tests/conformance/test_matrix/test_rows"
    )
    assert case_dir("api/tests/test_api.py::test_rows") == tmp_path / "python/tests/api/test_api/test_rows"


@pytest.mark.parametrize("mixed", [False, True])
def test_pytest_routes_assurance_sessions_and_tests_separately(tmp_path, mixed):
    project = tmp_path / "project"
    conformance = project / "conformance/tests"
    backend = project / "core/tests"
    conformance.mkdir(parents=True)
    backend.mkdir(parents=True)
    (conformance / "test_conformance_probe.py").write_text("def test_conformance(): pass\n")
    (backend / "test_backend_probe.py").write_text("def test_backend(): pass\n")
    artifacts = tmp_path / "recordings"
    env = {key: value for key, value in os.environ.items() if key not in {"COVERAGE_FILE", "TRACE_FILE"}}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "repo2ree_testbed.pytest_plugin",
            "--confcutdir",
            str(project),
            "-q",
            "conformance/tests",
            *(["core/tests"] if mixed else []),
        ],
        cwd=project,
        env={
            **env,
            "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "REPO2REE_TEST_RUN_DIR": str(artifacts),
            "REPO2REE_ASSURANCE_DIR": str(project / "test-artifacts/assurance"),
        },
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    (manifest,) = (project / "test-artifacts/assurance/tests/conformance").rglob("manifest.json")
    assert json.loads(manifest.read_text())["nodeid"].startswith("conformance/tests/")
    (session,) = (project / "test-artifacts/assurance/sessions").glob("*.json")
    document = json.loads(session.read_text())
    assert document["tests"] == 1
    assert document["artifact_domain"] == "assurance"
    assert not (artifacts / "python/tests/conformance").exists()
    if mixed:
        (backend_session,) = (artifacts / "python/sessions").glob("*.json")
        assert json.loads(backend_session.read_text())["tests"] == 1
        assert len(list((artifacts / "python/tests").rglob("manifest.json"))) == 1
    else:
        assert not (artifacts / "python").exists()
