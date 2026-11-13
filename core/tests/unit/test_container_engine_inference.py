"""A container file and an image archive, each proposed for the container engines the REE's scripts can use."""

from __future__ import annotations

from pathlib import Path

import pytest
from scriptinfer_helpers import FixedEngines, MemoryAccessor, docker_archive, machine

from repo2ree_core.author_recipes.inference import TargetInferenceResult, infer_scripts
from repo2ree_core.author_recipes.inference.experiment_environment_inputs import ExperimentEnvironmentInputs
from repo2ree_core.author_recipes.inference.machine import MachineInputs
from repo2ree_protocol.command import ScriptTargetSelectorArg
from repo2ree_protocol.inference import ContainerEngine, ContainerEnginesObservation
from repo2ree_ree.model import ReeDefinition
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

ARTIFACT = "runtime.tar"
DOCKER_BUILD = "single-project-root-dockerfile-v1"
PODMAN_BUILD = "single-project-root-containerfile-podman"
DOCKER_ACTIVATE = "docker-activate-experiment-environment-v1"
PODMAN_ACTIVATE = "podman-activate-experiment-environment"
BUILD = ScriptTargetSelectorArg(kind="build_experiment_environment")
ACTIVATE = ScriptTargetSelectorArg(kind="activate_experiment_environment")


def _project(root: Path, name: str = "Containerfile") -> Path:
    (root / name).write_text("FROM python:3.11-slim\n")
    (root / "main.py").write_text("print(1)\n")
    return root


def _infer(
    root: Path,
    *targets: ScriptTargetSelectorArg,
    on: MachineInputs | None = None,
    files: dict[str, bytes] | None = None,
) -> list[TargetInferenceResult]:
    inputs = ExperimentEnvironmentInputs(
        declared_experiment_environment_path=ARTIFACT, accessor=MemoryAccessor(files or {})
    )
    report = infer_scripts(
        root, list(targets), definition=ReeDefinition(name="Demo"), experiment_environment_inputs=inputs, machine=on
    )
    return report.results


def _rules(result: TargetInferenceResult) -> list[str]:
    return [candidate.inference_rule for candidate in result.candidates]


def _body(result: TargetInferenceResult) -> str:
    body = result.candidates[0].body
    assert body is not None
    return body


def _codes(result: TargetInferenceResult) -> set[str]:
    return {warning.code for warning in result.warnings}


@pytest.mark.parametrize(
    ("usable", "status", "rules"),
    [
        (("docker",), "complete", [DOCKER_BUILD]),
        (("podman",), "complete", [PODMAN_BUILD]),
        (("docker", "podman"), "needs_input", [DOCKER_BUILD, PODMAN_BUILD]),
        ((), "not_inferred", []),
    ],
)
def test_a_container_file_is_built_by_the_engines_the_machine_can_use(
    tmp_path: Path, usable: tuple[ContainerEngine, ...], status: str, rules: list[str]
) -> None:
    (build,) = _infer(_project(tmp_path), BUILD, on=machine(*usable))
    assert build.status == status
    assert _rules(build) == rules
    missing = {f"{engine}_unavailable" for engine in ("docker", "podman") if engine not in usable}
    assert missing <= _codes(build)


def test_either_file_name_is_built_by_either_engine(tmp_path: Path) -> None:
    (build,) = _infer(_project(tmp_path, "Dockerfile"), BUILD, on=machine("podman"))
    assert _rules(build) == [PODMAN_BUILD]
    assert "CONTAINERFILE=Dockerfile\n" in _body(build)


def test_the_podman_build_tags_the_name_podman_stores_and_saves_an_archive_either_engine_loads(tmp_path: Path) -> None:
    (build,) = _infer(_project(tmp_path), BUILD, on=machine("podman"))
    body = _body(build)
    assert "IMAGE_TAG=localhost/ree-runtime:demo\n" in body
    assert 'podman build \\\n    --file "$CONTAINERFILE"' in body
    assert "--format docker-archive" in body
    assert f"EXPERIMENT_ENVIRONMENT_ARTIFACT={ARTIFACT}\n" in body


def test_unknown_engines_propose_every_engine_for_confirmation(tmp_path: Path) -> None:
    (build,) = _infer(_project(tmp_path), BUILD)
    assert build.status == "needs_input"
    assert _rules(build) == [DOCKER_BUILD, PODMAN_BUILD]
    assert "container_engines_not_probed" in _codes(build)


def test_the_trace_records_what_the_probe_saw(tmp_path: Path) -> None:
    (build,) = _infer(_project(tmp_path), BUILD, on=machine("podman"))
    seen = [step.observed for step in build.decision.steps if isinstance(step.observed, ContainerEnginesObservation)]
    assert {observation.engine for observation in seen} == {"docker", "podman"}
    states = {engine.engine: engine.state for engine in seen[0].probe.engines}
    assert states == {"docker": "absent", "podman": "usable"}


def test_a_project_without_a_container_file_never_probes(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("\n")
    engines = FixedEngines("docker")
    _infer(tmp_path, BUILD, on=MachineInputs(engines=engines))
    assert engines.asked == 0


@pytest.mark.parametrize(("usable", "rules"), [(("docker",), [DOCKER_ACTIVATE]), (("podman",), [PODMAN_ACTIVATE])])
def test_an_image_archive_is_run_by_the_engine_the_machine_can_use(
    tmp_path: Path, usable: tuple[ContainerEngine, ...], rules: list[str]
) -> None:
    archive = docker_archive(["localhost/podman-hello:latest"])
    (activate,) = _infer(_project(tmp_path), ACTIVATE, on=machine(*usable), files={ARTIFACT: archive})
    assert _rules(activate) == rules


def test_the_podman_activation_loads_the_archive_unless_podman_holds_the_image(tmp_path: Path) -> None:
    archive = docker_archive(["localhost/podman-hello:latest"])
    (activate,) = _infer(_project(tmp_path), ACTIVATE, on=machine("podman"), files={ARTIFACT: archive})
    body = _body(activate)
    assert "IMAGE_TAG=localhost/podman-hello:latest\n" in body
    assert 'podman image exists "$IMAGE_TAG" || podman load --input "$EXPERIMENT_ENVIRONMENT_ARTIFACT"' in body
    assert 'exec podman run --rm -v "$PWD:$PWD" -w "$PWD" --entrypoint "" "$IMAGE_TAG" "$@"' in body


def test_an_unbuilt_generated_podman_build_is_activated_with_podman_even_where_docker_is_usable(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    (build,) = _infer(root, BUILD, on=machine("podman"))
    written = {RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT: _body(build).encode()}
    (activate,) = _infer(root, ACTIVATE, on=machine("docker", "podman"), files=written)
    assert _rules(activate) == [PODMAN_ACTIVATE]
    assert "IMAGE_TAG=localhost/ree-runtime:demo\n" in _body(activate)
