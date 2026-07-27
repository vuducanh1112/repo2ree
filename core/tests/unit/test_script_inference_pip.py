"""The pip-requirements build strategy (root-pip-requirements-v1).

The runtime for a plain requirements.txt repository is a Python virtual
environment, not a container: the generated build script creates a venv,
installs requirements.txt with pip, and packs the venv as the runtime artifact —
one self-contained shell script that introduces no Docker. A lone pip strategy
is confirmation-required (needs_input); a Dockerfile alongside it makes the two
strategies an explicit decision.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.authoring.script_inference import (
    ScriptTargetSelector,
    TargetInferenceResult,
    infer_scripts,
)


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return root


def _build(root: Path) -> TargetInferenceResult:
    return infer_scripts(root, [ScriptTargetSelector(kind="build")]).results[0]


def _pip_candidate(result: TargetInferenceResult):
    return next(c for c in result.candidates if c.inference_rule == "root-pip-requirements-v1")


def test_root_requirements_is_confirmation_required(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "numpy==1.26\npandas\n", "main.py": "x"})
    result = _build(tmp_path)
    assert result.status == "needs_input"
    assert result.application == "confirmation_required"
    candidate = _pip_candidate(result)
    assert candidate.status == "needs_input"
    assert candidate.body is not None


def test_pip_build_script_is_a_venv_build_with_no_docker(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n"})
    candidate = _pip_candidate(_build(tmp_path))
    body = candidate.body
    assert body is not None
    # It is the pip/venv technology, never Docker.
    assert "docker" not in body.lower()
    assert "python -m venv" in body
    assert 'pip" install --no-cache-dir --requirement "$REQUIREMENTS"' in body
    assert "tar -czf" in body


def test_pip_candidate_is_a_single_script_with_no_supporting_files(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n"})
    candidate = _pip_candidate(_build(tmp_path))
    # Inference produces only the shell script; the candidate model has no
    # supporting-files field at all.
    assert "supporting_files" not in candidate.model_dump()


def test_pip_candidate_warnings_are_non_blocking(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n"})
    candidate = _pip_candidate(_build(tmp_path))
    codes = {w.code for w in candidate.warnings}
    assert {"pip_environment_strategy", "python_version_unknown", "dependencies_not_locked"} <= codes
    assert not any(w.blocking for w in candidate.warnings)


def test_wrapper_archive_uses_wrapper_paths(tmp_path: Path) -> None:
    _tree(tmp_path, {"proj-main/requirements.txt": "flask\n", "proj-main/main.py": "x"})
    candidate = _pip_candidate(_build(tmp_path))
    assert candidate.body is not None
    assert "REQUIREMENTS=proj-main/requirements.txt\n" in candidate.body
    assert "RUNTIME_ARTIFACT=proj-main/.repo2ree/artifacts/runtime-venv.tar.gz\n" in candidate.body


def test_dockerfile_and_requirements_is_a_decision(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n", "Dockerfile": "FROM x\n"})
    result = _build(tmp_path)
    assert result.status == "needs_input"
    rules = sorted(c.inference_rule for c in result.candidates)
    assert rules == ["root-pip-requirements-v1", "single-project-root-dockerfile-v1"]


def test_nested_requirements_does_not_fire(tmp_path: Path) -> None:
    # A requirements.txt below the project root is not the root-pip shape.
    _tree(tmp_path, {"subpkg/requirements.txt": "flask\n", "README.md": "hi", "main.py": "x"})
    result = _build(tmp_path)
    assert result.status == "not_inferred"
    assert result.candidates == []


def test_pip_candidate_bytes_are_deterministic(tmp_path: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("other")
    files = {"requirements.txt": "flask==3.0\n"}
    _tree(tmp_path, files)
    _tree(other, files)
    assert _pip_candidate(_build(tmp_path)).body == _pip_candidate(_build(other)).body
