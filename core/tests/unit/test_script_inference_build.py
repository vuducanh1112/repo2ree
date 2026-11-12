"""End-to-end build inference: positive candidates, decline cases, determinism.

Most of the precision policy lives in decline behavior, so these lean on the
Docker decline table from the design doc.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.author_recipes.inference import (
    TargetInferenceResult,
    infer_scripts,
)
from repo2ree_core.author_recipes.inference.experiment_environment_inputs import ExperimentEnvironmentInputs
from repo2ree_protocol.command import ScriptTargetSelectorArg
from repo2ree_protocol.inference import LogicalRootObservation
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import ExperimentEnvironmentDefinition, ReeDefinition
from repo2ree_ree.primitives import ExperimentEnvironmentPath


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return root


def _build(root: Path, **intent_kwargs: object) -> TargetInferenceResult:
    experiment_environment = intent_kwargs.pop("experiment_environment", None)
    name = str(intent_kwargs.pop("name", ""))
    assert not intent_kwargs
    definition = ReeDefinition(
        name=name,
        experiment_environment=(
            ExperimentEnvironmentDefinition(
                build_experiment_environment_script_digest=digest_bytes(b"build_experiment_environment"),
                build_experiment_environment_script_size=5,
                artifact_path=ExperimentEnvironmentPath(str(experiment_environment)),
            )
            if experiment_environment
            else None
        ),
    )
    report = infer_scripts(
        root,
        [ScriptTargetSelectorArg(kind="build_experiment_environment")],
        definition=definition,
        # The declared experiment environment path reaches inference on the experiment environment inputs, not
        # on the definition — the handler builds it there. Passing only the
        # definition would leave the declaration invisible to the renderer.
        experiment_environment_inputs=ExperimentEnvironmentInputs(
            declared_experiment_environment_path=str(experiment_environment) if experiment_environment else None
        ),
    )
    return report.results[0]


def _body(result: TargetInferenceResult) -> str:
    body = result.candidates[0].body
    assert body is not None
    return body


def test_flat_single_dockerfile_is_complete_automatic(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM python:3.11-slim\n", "main.py": "print(1)\n"})
    result = _build(tmp_path)
    assert result.status == "complete"
    assert result.application == "automatic_allowed"
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    body = _body(result)
    assert candidate.target.path == "ree-scripts/build_experiment_environment.sh"
    assert "DOCKERFILE=Dockerfile\n" in body
    assert "BUILD_CONTEXT=.\n" in body
    # No blocking warning on an automatic candidate.
    assert not any(w.blocking for w in result.warnings)


def test_single_wrapper_uses_wrapper_as_build_context(tmp_path: Path) -> None:
    _tree(tmp_path, {"proj-main/Dockerfile": "FROM x\n", "proj-main/main.py": "x"})
    result = _build(tmp_path)
    assert result.status == "complete"
    body = _body(result)
    assert "DOCKERFILE=proj-main/Dockerfile\n" in body
    assert "BUILD_CONTEXT=proj-main\n" in body


def test_two_root_dockerfiles_block(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "x", "Dockerfile.dev": "y"})
    result = _build(tmp_path)
    assert result.status == "not_inferred"
    assert result.candidates == []
    assert any(w.code == "multiple_dockerfiles" and w.blocking for w in result.warnings)


def test_nested_dockerfile_is_ambiguous(tmp_path: Path) -> None:
    _tree(tmp_path, {"docker/Dockerfile": "x", "README.md": "hi", "main.py": "y"})
    result = _build(tmp_path)
    # Root stays "." (several meaningful entries); nested Dockerfile is ambiguous.
    root_obs = result.decision.steps[0].observed
    assert isinstance(root_obs, LogicalRootObservation)
    assert root_obs.path == "."
    assert result.status == "not_inferred"
    assert any(w.code == "ambiguous_build_context" for w in result.warnings)


def test_no_dockerfile_is_not_inferred_with_full_trace(tmp_path: Path) -> None:
    _tree(tmp_path, {"main.py": "x"})
    result = _build(tmp_path)
    assert result.status == "not_inferred"
    assert result.candidates == []
    # A decline still carries the complete trace to its result node.
    assert result.decision.result_node == "build-not-inferred"
    kinds = [step.kind for step in result.decision.steps]
    assert kinds[0] == "check"
    assert "fork" in kinds
    assert "resolve" in kinds
    assert kinds[-1] == "result"


def test_experiment_environment_artifact_honors_the_declared_experiment_environment(tmp_path: Path) -> None:
    # experiment_environment_path is where the build is expected to leave its artifact, and the
    # build fails its post-condition when nothing lands there — so the generated
    # recipe writes exactly where the REE declares.
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _build(tmp_path, experiment_environment="ree-out/prebuilt.tar")
    assert "EXPERIMENT_ENVIRONMENT_ARTIFACT=ree-out/prebuilt.tar\n" in _body(result)


def test_experiment_environment_artifact_falls_back_to_the_strategy_default_when_undeclared(tmp_path: Path) -> None:
    # The fallback covers inference running before a declaration exists — a
    # freshly seeded script on an REE whose experiment environment is not yet declared.
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    assert "EXPERIMENT_ENVIRONMENT_ARTIFACT=.repo2ree/artifacts/runtime.tar\n" in _body(_build(tmp_path))


def test_image_tag_is_derived_from_the_ree_name(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    assert "IMAGE_TAG=ree-runtime:python-hello-world\n" in _body(_build(tmp_path, name="Python Hello World"))


def test_image_tag_falls_back_when_name_is_empty(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    assert "IMAGE_TAG=ree-runtime:ree\n" in _body(_build(tmp_path, name=""))


def test_candidate_bytes_are_deterministic(tmp_path: Path, tmp_path_factory) -> None:
    other = tmp_path_factory.mktemp("other")
    files = {"Dockerfile": "FROM x\n", "main.py": "y\n"}
    _tree(tmp_path, files)
    _tree(other, files)
    a = _body(_build(tmp_path))
    b = _body(_build(other))
    assert a == b


def test_candidate_records_dockerfile_dependency(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    candidate = _build(tmp_path).candidates[0]
    source = [dep for dep in candidate.dependencies if dep.kind == "source"]
    assert len(source) == 1
    assert source[0].path == "Dockerfile"
    assert source[0].digest.startswith("sha256:")
    assert candidate.validation.status == "not_run"
    assert candidate.validation.script_digest is not None


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        ("ree-out/prebuilt.tar", "ree-out/prebuilt.tar"),
        (None, ".repo2ree/artifacts/runtime.tar"),
    ],
)
def test_candidate_records_the_experiment_environment_path_it_writes_to(
    tmp_path: Path, declared: str | None, expected: str
) -> None:
    # Declared or defaulted, the path is part of what justifies these bytes:
    # move it and regeneration renders differently. The dependency does not say
    # which of the two it was — a client compares it against its own declaration
    # — so both cases record the same role.
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _build(tmp_path, experiment_environment=declared) if declared else _build(tmp_path)
    candidate = result.candidates[0]
    declaration = [dep for dep in candidate.dependencies if dep.kind == "experiment_environment_declaration"]
    assert len(declaration) == 1
    assert declaration[0].path == expected
    assert declaration[0].role == "experiment_environment"
    # The reported path is worthless unless it is the one the script writes to.
    assert f"EXPERIMENT_ENVIRONMENT_ARTIFACT={expected}\n" in _body(result)
