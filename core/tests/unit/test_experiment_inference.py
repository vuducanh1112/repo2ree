"""End-to-end experiment-run inference: declaration gate + capture scaffold."""

from __future__ import annotations

from pathlib import Path

from scriptinfer_helpers import MemoryAccessor, docker_archive, venv_archive

from repo2ree_core.authoring.script_inference import ScriptTargetSelector, TargetInferenceResult, infer_scripts
from repo2ree_core.authoring.script_inference.runtime_inputs import RuntimeInputs
from repo2ree_core.domain.experiment import Experiment
from repo2ree_core.domain.ree.intent import ReeIntent

_DOCKER_RUNTIME = ".repo2ree/artifacts/runtime.tar"
_VENV_RUNTIME = ".repo2ree/artifacts/runtime-venv.tar.gz"


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    return root


def _experiment(
    root: Path,
    *,
    name: str,
    runtime: str,
    files: dict[str, bytes],
    experiments: list[Experiment],
) -> TargetInferenceResult:
    intent = ReeIntent(name="Demo", runtime=runtime, experiments=experiments)
    inputs = RuntimeInputs(declared_runtime_path=runtime, experiments=experiments, accessor=MemoryAccessor(files))
    report = infer_scripts(
        root,
        [ScriptTargetSelector(kind="experiment_run", experiment_name=name)],
        intent=intent,
        runtime_inputs=inputs,
    )
    return report.results[0]


def _codes(result: TargetInferenceResult) -> set[str]:
    return {w.code for w in result.warnings}


def test_declared_experiment_with_docker_runtime_captures_log(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    exp = Experiment(name="exp one", output_paths=["results/exp-one.log"])
    result = _experiment(
        tmp_path,
        name="exp one",
        runtime=_DOCKER_RUNTIME,
        files={_DOCKER_RUNTIME: docker_archive(["ree-runtime:demo"])},
        experiments=[exp],
    )
    assert result.status == "needs_input"
    assert result.application == "confirmation_required"
    body = result.candidates[0].body or ""
    assert result.candidates[0].inference_rule == "docker-runtime-experiment-v1"
    assert "RUN_LOG=results/exp-one.log" in body
    assert '>"$RUN_LOG"' in body
    assert "experiment_command_missing" in _codes(result)
    # The log is a declared output, so no output-declaration warning.
    assert "experiment_output_declaration_missing" not in _codes(result)


def test_undeclared_output_path_warns(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    exp = Experiment(name="exp one")  # no output_paths declared
    result = _experiment(
        tmp_path,
        name="exp one",
        runtime=_DOCKER_RUNTIME,
        files={_DOCKER_RUNTIME: docker_archive(["ree-runtime:demo"])},
        experiments=[exp],
    )
    assert "experiment_output_declaration_missing" in _codes(result)


def test_undeclared_experiment_blocks(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _experiment(
        tmp_path,
        name="ghost",
        runtime=_DOCKER_RUNTIME,
        files={_DOCKER_RUNTIME: docker_archive(["ree-runtime:demo"])},
        experiments=[Experiment(name="real")],
    )
    assert result.status == "not_inferred"
    assert result.candidates == []
    assert "experiment_not_declared" in _codes(result)


def test_venv_runtime_experiment(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n"})
    exp = Experiment(name="run", output_paths=["results/run.log"])
    result = _experiment(
        tmp_path,
        name="run",
        runtime=_VENV_RUNTIME,
        files={_VENV_RUNTIME: venv_archive()},
        experiments=[exp],
    )
    assert result.status == "needs_input"
    assert result.candidates[0].inference_rule == "venv-runtime-experiment-v1"
    body = result.candidates[0].body or ""
    assert '"$@" >"$RUN_LOG"' in body


def test_missing_runtime_blocks_even_for_declared_experiment(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    result = _experiment(
        tmp_path,
        name="run",
        runtime=_DOCKER_RUNTIME,
        files={},
        experiments=[Experiment(name="run")],
    )
    assert result.status == "not_inferred"
    assert "runtime_artifact_missing" in _codes(result)
