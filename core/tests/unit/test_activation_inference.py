"""End-to-end activation-run inference: runtime-contract resolution + scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest
from scriptinfer_helpers import MemoryAccessor, docker_archive, not_an_archive, oci_archive, venv_archive

from repo2ree_core.author_recipes.inference import TargetInferenceResult, infer_scripts
from repo2ree_core.author_recipes.inference.experiment_environment_inputs import ExperimentEnvironmentInputs
from repo2ree_protocol.command import ScriptTargetSelectorArg
from repo2ree_ree.model import ReeDefinition

_DOCKER_EXPERIMENT_ENVIRONMENT = ".repo2ree/artifacts/runtime.tar"
_VENV_EXPERIMENT_ENVIRONMENT = ".repo2ree/artifacts/runtime-venv.tar.gz"


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return root


def _activation(
    root: Path, *, experiment_environment: str | None, files: dict[str, bytes], name: str = "Demo"
) -> TargetInferenceResult:
    definition = ReeDefinition(name=name)
    inputs = ExperimentEnvironmentInputs(
        declared_experiment_environment_path=experiment_environment, accessor=MemoryAccessor(files)
    )
    report = infer_scripts(
        root,
        [ScriptTargetSelectorArg(kind="activation_run")],
        definition=definition,
        experiment_environment_inputs=inputs,
    )
    return report.results[0]


def _codes(result: TargetInferenceResult) -> set[str]:
    return {w.code for w in result.warnings}


def test_docker_experiment_environment_yields_confirmation_required_scaffold(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n", "main.py": "y"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: docker_archive(["ree-runtime:demo"], cmd=["python", "main.py"])},
    )
    assert result.status == "needs_input"
    assert result.application == "confirmation_required"
    candidate = result.candidates[0]
    assert candidate.inference_rule == "docker-runtime-activation-v1"
    body = candidate.body or ""
    # The docker plumbing is present, the command is fail-closed, and the
    # detected CMD is offered only as a commented example.
    assert "docker load --input" in body
    assert "set --\n" in body
    assert "exit 64" in body
    assert "#   set -- python main.py" in body
    assert "activation_command_missing" in _codes(result)


def test_oci_experiment_environment_resolves_like_a_legacy_docker_archive(tmp_path: Path) -> None:
    # A containerd-image-store ``docker save`` writes an OCI archive (no
    # manifest.json); it must resolve the same docker experiment environment contract so
    # activation is inferred rather than falling to not_inferred.
    _tree(tmp_path, {"Dockerfile": "FROM x\n", "main.py": "y"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: oci_archive("ree-runtime:demo", cmd=["python", "main.py"])},
    )
    assert result.status == "needs_input"
    candidate = result.candidates[0]
    assert candidate.inference_rule == "docker-runtime-activation-v1"
    body = candidate.body or ""
    assert "IMAGE_TAG=ree-runtime:demo" in body
    # The OCI image's declared command surfaces as a commented example, exactly
    # like the legacy path.
    assert "#   set -- python main.py" in body


def test_venv_experiment_environment_yields_venv_scaffold(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n", "main.py": "y"})
    result = _activation(
        tmp_path,
        experiment_environment=_VENV_EXPERIMENT_ENVIRONMENT,
        files={_VENV_EXPERIMENT_ENVIRONMENT: venv_archive()},
    )
    assert result.status == "needs_input"
    candidate = result.candidates[0]
    assert candidate.inference_rule == "venv-runtime-activation-v1"
    body = candidate.body or ""
    assert "tar -xzf" in body
    assert 'PATH="$VENV_DIR/bin:$PATH"' in body
    # No ``command`` in the archive -> restore to the repo2ree default location,
    # and warn that the location was assumed rather than recovered.
    assert "VENV_DIR=/tmp/ree-venv" in body
    assert "venv_restore_dir_assumed" in _codes(result)


def test_venv_scaffold_restores_to_the_recovered_build_dir(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n", "main.py": "y"})
    # A venv built somewhere other than the default must be restored there, since
    # a venv bakes absolute paths. The recovered path flows into the scaffold and
    # no "assumed" warning is raised because the location came from the metadata.
    archive = venv_archive(top_dir="ree-venv", command="/usr/bin/python3 -m venv /opt/envs/ree-venv")
    result = _activation(
        tmp_path, experiment_environment=_VENV_EXPERIMENT_ENVIRONMENT, files={_VENV_EXPERIMENT_ENVIRONMENT: archive}
    )
    body = result.candidates[0].body or ""
    assert "VENV_DIR=/opt/envs/ree-venv" in body
    assert "venv_restore_dir_assumed" not in _codes(result)


def test_no_experiment_environment_declared_blocks(tmp_path: Path) -> None:
    _tree(tmp_path, {"main.py": "y"})
    result = _activation(tmp_path, experiment_environment=None, files={})
    assert result.status == "not_inferred"
    assert result.candidates == []
    assert "experiment_environment_declaration_missing" in _codes(result)


def test_missing_artifact_blocks(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _activation(tmp_path, experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT, files={})
    assert result.status == "not_inferred"
    assert {"experiment_environment_artifact_missing", "experiment_environment_not_resolved"} <= _codes(result)


def test_experiment_environment_outside_project_root_blocks(tmp_path: Path) -> None:
    _tree(tmp_path, {"proj-main/Dockerfile": "FROM x\n", "proj-main/main.py": "y"})
    # Logical root peels to proj-main/; an experiment environment above it escapes.
    result = _activation(tmp_path, experiment_environment="elsewhere/runtime.tar", files={})
    assert result.status == "not_inferred"
    assert "experiment_environment_outside_project_root" in _codes(result)


def test_invalid_archive_blocks(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: not_an_archive()},
    )
    assert result.status == "not_inferred"
    assert "experiment_environment_archive_invalid" in _codes(result)


def test_multiple_image_refs_block_without_guessing(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: docker_archive(["ree-runtime:a", "ree-runtime:b"])},
    )
    assert result.status == "not_inferred"
    assert "multiple_experiment_environment_images" in _codes(result)


def test_no_image_ref_blocks(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: docker_archive([])},
    )
    assert result.status == "not_inferred"
    assert "experiment_environment_image_ref_missing" in _codes(result)


def test_shell_form_command_is_offered_verbatim(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={
            _DOCKER_EXPERIMENT_ENVIRONMENT: docker_archive(["ree-runtime:demo"], entrypoint="python main.py | tee out")
        },
    )
    body = result.candidates[0].body or ""
    assert "set -- sh -c 'python main.py | tee out'" in body
    assert "shell_required_in_experiment_environment" in _codes(result)


@pytest.mark.parametrize("archive", [docker_archive(["ree-runtime:demo"]), venv_archive()])
def test_trace_always_reaches_a_result_node(tmp_path: Path, archive: bytes) -> None:
    experiment_environment = _DOCKER_EXPERIMENT_ENVIRONMENT if b"manifest" in archive else _VENV_EXPERIMENT_ENVIRONMENT
    _tree(tmp_path, {"Dockerfile": "FROM x\n", "requirements.txt": "flask\n"})
    result = _activation(
        tmp_path, experiment_environment=experiment_environment, files={experiment_environment: archive}
    )
    assert result.decision.result_node
    assert result.decision.steps
