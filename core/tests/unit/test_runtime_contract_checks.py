"""Focused runtime-contract tests: provenance and command extraction.

End-to-end coverage of the blocked/resolved branches lives in the activation and
experiment suites; this pins the two subtler behaviours — the pre-build
``unchanged_generated_build`` provenance and Docker config command parsing.
"""

from __future__ import annotations

from pathlib import Path

from scriptinfer_helpers import MemoryAccessor, docker_archive

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.script_inference import ScriptTargetSelector, infer_scripts
from repo2ree_core.script_inference.build_regeneration import expected_build_for_runtime
from repo2ree_core.script_inference.models import DecisionContext
from repo2ree_core.script_inference.policy import default_policy
from repo2ree_core.script_inference.repository_facts import scan_repository
from repo2ree_core.script_inference.runtime_inputs import RuntimeInputs

_DOCKER_RUNTIME = ".repo2ree/artifacts/runtime.tar"
_VENV_RUNTIME = ".repo2ree/artifacts/runtime-venv.tar.gz"


def _tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        fp = root / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)


def _generated_build_body(root: Path, runtime: str) -> str:
    ctx = DecisionContext(facts=scan_repository(root), policy=default_policy(), ree_name="Demo")
    expected = expected_build_for_runtime(ctx, runtime)
    assert expected is not None
    return expected.body


def _provenances(result) -> set[str]:
    return {
        step.observed.provenance
        for step in result.decision.steps
        if getattr(step.observed, "kind", None) == "runtime_contract" and getattr(step.observed, "provenance", None)
    }


def test_unchanged_generated_docker_build_resolves_before_the_artifact_exists(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM python:3.11-slim\n", "main.py": "y"})
    body = _generated_build_body(tmp_path, _DOCKER_RUNTIME)
    # The artifact itself is absent; only the written build script is present.
    inputs = RuntimeInputs(
        declared_runtime_path=_DOCKER_RUNTIME,
        accessor=MemoryAccessor({RESERVED_BUILD_SCRIPT: body.encode()}),
    )
    result = infer_scripts(
        tmp_path,
        [ScriptTargetSelector(kind="activation_run")],
        intent=ReeIntent(name="Demo", runtime=_DOCKER_RUNTIME),
        runtime_inputs=inputs,
    ).results[0]
    assert result.status == "needs_input"
    assert result.candidates[0].inference_rule == "docker-runtime-activation-v1"
    assert "unchanged_generated_build" in _provenances(result)


def test_unchanged_generated_venv_build_resolves_before_the_artifact_exists(tmp_path: Path) -> None:
    _tree(tmp_path, {"requirements.txt": "flask\n", "main.py": "y"})
    body = _generated_build_body(tmp_path, _VENV_RUNTIME)
    inputs = RuntimeInputs(
        declared_runtime_path=_VENV_RUNTIME,
        accessor=MemoryAccessor({RESERVED_BUILD_SCRIPT: body.encode()}),
    )
    result = infer_scripts(
        tmp_path,
        [ScriptTargetSelector(kind="activation_run")],
        intent=ReeIntent(name="Demo", runtime=_VENV_RUNTIME),
        runtime_inputs=inputs,
    ).results[0]
    assert result.candidates[0].inference_rule == "venv-runtime-activation-v1"
    assert "unchanged_generated_build" in _provenances(result)


def test_edited_build_script_does_not_resolve(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM python:3.11-slim\n", "main.py": "y"})
    inputs = RuntimeInputs(
        declared_runtime_path=_DOCKER_RUNTIME,
        accessor=MemoryAccessor({RESERVED_BUILD_SCRIPT: b"#!/bin/sh\n# hand-edited\n"}),
    )
    result = infer_scripts(
        tmp_path,
        [ScriptTargetSelector(kind="activation_run")],
        intent=ReeIntent(name="Demo", runtime=_DOCKER_RUNTIME),
        runtime_inputs=inputs,
    ).results[0]
    assert result.status == "not_inferred"
    assert "runtime_artifact_missing" in {w.code for w in result.warnings}


def test_docker_entrypoint_and_cmd_combine_into_one_argv_example(tmp_path: Path) -> None:
    _tree(tmp_path, {"Dockerfile": "FROM x\n"})
    inputs = RuntimeInputs(
        declared_runtime_path=_DOCKER_RUNTIME,
        accessor=MemoryAccessor(
            {_DOCKER_RUNTIME: docker_archive(["ree-runtime:demo"], entrypoint=["python"], cmd=["main.py", "--fast"])}
        ),
    )
    result = infer_scripts(
        tmp_path,
        [ScriptTargetSelector(kind="activation_run")],
        intent=ReeIntent(name="Demo", runtime=_DOCKER_RUNTIME),
        runtime_inputs=inputs,
    ).results[0]
    body = result.candidates[0].body or ""
    assert "#   set -- python main.py --fast" in body
