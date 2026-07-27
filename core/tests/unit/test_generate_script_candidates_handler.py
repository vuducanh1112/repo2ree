"""Unit coverage for the generate_script_candidates operations handler.

Points ``ReeLayout.in_workbench`` at a tmp root (the seam the other handler
tests use) and exercises the precondition guard, the read-only success path, and
that inference reads the immutable upstream tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.operations.handlers import generate_script_candidates as handler
from repo2ree_core.ree.layout import ReeLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_protocol.command import GenerateScriptCandidatesArgs, ScriptTargetSelectorArg


def _silent_log(*_: object) -> None:
    return None


def _never_canceled() -> bool:
    return False


def _store_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeStore:
    store = ReeStore(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return store


def _seed_upstream(tmp_path: Path, files: dict[str, str]) -> None:
    upstream = tmp_path / "upstream"
    for rel, content in files.items():
        fp = upstream / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)


def _args(*kinds: str) -> GenerateScriptCandidatesArgs:
    targets = [ScriptTargetSelectorArg.model_validate({"kind": k}) for k in kinds]
    return GenerateScriptCandidatesArgs(targets=targets)


def test_canceled_before_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    _seed_upstream(tmp_path, {"Dockerfile": "x"})
    result = handler.handle_generate_script_candidates(_args("build"), log=_silent_log, is_canceled=lambda: True)
    assert result.status == "canceled"


def test_no_targets_is_validation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    result = handler.handle_generate_script_candidates(
        GenerateScriptCandidatesArgs(targets=[]), log=_silent_log, is_canceled=_never_canceled
    )
    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "validation"


def test_missing_upstream_is_precondition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)  # ensure_dirs does not create upstream
    (tmp_path / "upstream").rmdir() if (tmp_path / "upstream").is_dir() else None
    result = handler.handle_generate_script_candidates(_args("build"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "failed"
    assert result.failure is not None
    assert result.failure.category == "precondition"


def test_build_success_returns_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    _seed_upstream(tmp_path, {"Dockerfile": "FROM x\n", "main.py": "y"})
    result = handler.handle_generate_script_candidates(_args("build"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "succeeded"
    report = result.outputs
    assert report["schema_version"] == 1
    (target_result,) = report["results"]
    assert target_result["status"] == "complete"
    assert target_result["candidates"][0]["target"]["path"] == "ree-scripts/build_script.sh"


def test_inference_ignores_overlay_generated_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A Dockerfile written only into the overlay/workspace must not be seen: the
    # scan is over the immutable upstream tree.
    _store_at(tmp_path, monkeypatch)
    _seed_upstream(tmp_path, {"main.py": "y"})
    overlay_dockerfile = tmp_path / "overlay" / "Dockerfile"
    overlay_dockerfile.parent.mkdir(parents=True, exist_ok=True)
    overlay_dockerfile.write_text("FROM x\n")
    result = handler.handle_generate_script_candidates(_args("build"), log=_silent_log, is_canceled=_never_canceled)
    assert result.status == "succeeded"
    assert result.outputs["results"][0]["status"] == "not_inferred"
