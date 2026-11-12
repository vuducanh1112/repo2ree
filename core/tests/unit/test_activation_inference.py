"""End-to-end inference of what runs in the experiment environment: its contract, activate script, and run scaffold.

The run scaffold is an experiment's: it shares the contract subgraph with the activate script.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from scriptinfer_helpers import MemoryAccessor, docker_archive, not_an_archive, oci_archive, venv_archive

from repo2ree_core.author_recipes.inference import TargetInferenceResult, infer_scripts
from repo2ree_core.author_recipes.inference.experiment_environment_inputs import ExperimentEnvironmentInputs
from repo2ree_protocol.command import ScriptTargetSelectorArg
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import ExperimentDefinition, ReeDefinition
from repo2ree_ree.primitives import OverlayPath
from repo2ree_ree.reserved_paths import experiment_run_script_path

_DOCKER_EXPERIMENT_ENVIRONMENT = ".repo2ree/artifacts/runtime.tar"
_VENV_EXPERIMENT_ENVIRONMENT = ".repo2ree/artifacts/runtime-venv.tar.gz"
_EXPERIMENT = ExperimentDefinition(
    name="run",
    run_script_path=OverlayPath(experiment_run_script_path("run")),
    run_script_digest=digest_bytes(b"script"),
    run_script_size=6,
)


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return root


def _activation(
    root: Path,
    *,
    experiment_environment: str | None,
    files: dict[str, bytes],
    name: str = "Demo",
    kind: Literal["experiment_run", "activate_experiment_environment"] = "experiment_run",
) -> TargetInferenceResult:
    definition = ReeDefinition(name=name, experiments=(_EXPERIMENT,))
    inputs = ExperimentEnvironmentInputs(
        declared_experiment_environment_path=experiment_environment,
        experiments=[_EXPERIMENT],
        accessor=MemoryAccessor(files),
    )
    selector = (
        ScriptTargetSelectorArg(kind=kind, experiment_name=_EXPERIMENT.name)
        if kind == "experiment_run"
        else ScriptTargetSelectorArg(kind=kind)
    )
    report = infer_scripts(root, [selector], definition=definition, experiment_environment_inputs=inputs)
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
    assert candidate.inference_rule == "docker-runtime-experiment-v1"
    body = candidate.body or ""
    assert "docker load" not in body
    assert "set --\n" in body
    assert "exit 64" in body
    assert "#   set -- python main.py" in body
    assert "experiment_command_missing" in _codes(result)
    activate = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: docker_archive(["ree-runtime:demo"], cmd=["python", "main.py"])},
        kind="activate_experiment_environment",
    ).candidates[0]
    assert activate.inference_rule == "docker-activate-experiment-environment-v1"
    assert "docker load --input" in (activate.body or "")
    assert 'exec docker run --rm -v "$PWD:$PWD" -w "$PWD" --entrypoint "" "$IMAGE_TAG" "$@"' in (activate.body or "")
    assert "exit 64" not in (activate.body or "")


def test_oci_experiment_environment_resolves_like_a_legacy_docker_archive(tmp_path: Path) -> None:
    # A containerd-image-store ``docker save`` writes an OCI archive (no
    # manifest.json); it must resolve the same docker experiment environment contract so
    # what runs in it is inferred rather than falling to not_inferred.
    _tree(tmp_path, {"Dockerfile": "FROM x\n", "main.py": "y"})
    result = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: oci_archive("ree-runtime:demo", cmd=["python", "main.py"])},
    )
    assert result.status == "needs_input"
    candidate = result.candidates[0]
    assert candidate.inference_rule == "docker-runtime-experiment-v1"
    body = candidate.body or ""
    assert "#   set -- python main.py" in body
    activate = _activation(
        tmp_path,
        experiment_environment=_DOCKER_EXPERIMENT_ENVIRONMENT,
        files={_DOCKER_EXPERIMENT_ENVIRONMENT: oci_archive("ree-runtime:demo", cmd=["python", "main.py"])},
        kind="activate_experiment_environment",
    )
    assert "IMAGE_TAG=ree-runtime:demo" in (activate.candidates[0].body or "")


def test_venv_experiment_environment_yields_venv_scaffold(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n", "main.py": "y"})
    result = _activation(
        tmp_path,
        experiment_environment=_VENV_EXPERIMENT_ENVIRONMENT,
        files={_VENV_EXPERIMENT_ENVIRONMENT: venv_archive()},
        kind="activate_experiment_environment",
    )
    assert result.status == "needs_input"
    candidate = result.candidates[0]
    assert candidate.inference_rule == "venv-activate-experiment-environment-v1"
    body = candidate.body or ""
    assert 'exec "$@"' in body
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
        tmp_path,
        experiment_environment=_VENV_EXPERIMENT_ENVIRONMENT,
        files={_VENV_EXPERIMENT_ENVIRONMENT: archive},
        kind="activate_experiment_environment",
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
