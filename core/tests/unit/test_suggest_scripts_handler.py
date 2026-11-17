"""Unit coverage for the suggest_scripts operations handler.

Runs the handler against an REE in a tmp root and exercises the precondition
guard, the read-only success path, and that inference reads the immutable
upstream tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scriptinfer_helpers import FixedEngines

from repo2ree_core.operations.handlers.author import suggest_scripts as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import ScriptTargetSelectorArg, SuggestScriptsArgs


@pytest.fixture(autouse=True)
def _docker_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests never probe the machine they run on: its scripts can use Docker alone."""
    monkeypatch.setattr(handler, "engine_probe", lambda _layout: FixedEngines("docker"))


def _silent_log(*_: object) -> None:
    return None


def _never_canceled() -> bool:
    return False


def _store_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeDirectory:
    store = ReeDirectory(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    return store


def _seed_upstream(tmp_path: Path, files: dict[str, str]) -> None:
    upstream = tmp_path / "upstream"
    for rel, content in files.items():
        fp = upstream / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)


def _args(*kinds: str) -> SuggestScriptsArgs:
    targets = [ScriptTargetSelectorArg.model_validate({"kind": k}) for k in kinds]
    return SuggestScriptsArgs(targets=targets)


def test_no_targets_is_validation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    result = handler.handle_suggest_scripts(
        SuggestScriptsArgs(targets=[]),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=ReeLayout(root=tmp_path),
    )
    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "validation"


def test_missing_upstream_is_precondition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)  # ensure_dirs does not create upstream
    (tmp_path / "upstream").rmdir() if (tmp_path / "upstream").is_dir() else None
    result = handler.handle_suggest_scripts(
        _args("build_experiment_environment"),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=ReeLayout(root=tmp_path),
    )
    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"


def test_build_success_returns_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    _seed_upstream(tmp_path, {"Dockerfile": "FROM x\n", "main.py": "y"})
    result = handler.handle_suggest_scripts(
        _args("build_experiment_environment"),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=ReeLayout(root=tmp_path),
    )
    assert result.status == "succeeded"
    report = result.outputs
    assert report["schema_version"] == 1
    (target_result,) = report["results"]
    assert target_result["status"] == "complete"
    assert target_result["candidates"][0]["target"]["path"] == "ree-scripts/build_experiment_environment.sh"


def test_inference_ignores_overlay_generated_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A Dockerfile written only into the overlay/workspace must not be seen: the
    # scan is over the immutable upstream tree.
    _store_at(tmp_path, monkeypatch)
    _seed_upstream(tmp_path, {"main.py": "y"})
    overlay_dockerfile = tmp_path / "overlay" / "Dockerfile"
    overlay_dockerfile.parent.mkdir(parents=True, exist_ok=True)
    overlay_dockerfile.write_text("FROM x\n")
    result = handler.handle_suggest_scripts(
        _args("build_experiment_environment"),
        log=_silent_log,
        is_canceled=_never_canceled,
        layout=ReeLayout(root=tmp_path),
    )
    assert result.status == "succeeded"
    assert result.outputs["results"][0]["status"] == "not_inferred"
