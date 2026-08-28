"""Unit coverage for the lint_scripts operations handler.

Points ``ReeLayout.in_workbench`` at a tmp root (the seam the other handler
tests use) and covers the validation guard, reading scripts out of the overlay,
and the distinction between a script that is absent and one that is empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.operations.handlers.author import lint_scripts as handler
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_protocol.command import LintScriptsArgs, ScriptTargetSelectorArg
from repo2ree_protocol.result import ActionResult


def _silent_log(*_: object) -> None:
    return None


def _never_canceled() -> bool:
    return False


def _store_at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeDirectory:
    store = ReeDirectory(ReeLayout(root=tmp_path))
    store.ensure_dirs()
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
    return store


def _write_overlay(tmp_path: Path, rel: str, content: str) -> None:
    path = tmp_path / "overlay" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _args(*kinds: str) -> LintScriptsArgs:
    return LintScriptsArgs(targets=[ScriptTargetSelectorArg.model_validate({"kind": k}) for k in kinds])


def _run(args: LintScriptsArgs) -> ActionResult:
    return handler.handle_lint_scripts(args, log=_silent_log, is_canceled=_never_canceled)


def test_no_targets_is_a_validation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    result = _run(LintScriptsArgs(targets=[]))
    assert result.status == "failed"


def test_a_written_script_is_read_from_the_overlay_and_reported_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store_at(tmp_path, monkeypatch)
    _write_overlay(tmp_path, RESERVED_BUILD_SCRIPT, "#!/usr/bin/env sh\nset -eu\ndocker build .\n")

    result = _run(_args("build"))

    assert result.status == "succeeded"
    (report,) = result.outputs["reports"]
    assert report["target"]["path"] == RESERVED_BUILD_SCRIPT
    assert result.outputs["missing_scripts"] == []


def test_an_unwritten_script_is_listed_rather_than_reported_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # "Nothing written yet" and "written, and says nothing" are different things
    # to tell an author, so an absent script never becomes an empty report.
    _store_at(tmp_path, monkeypatch)

    result = _run(_args("build"))

    assert result.status == "succeeded"
    assert result.outputs["reports"] == []
    assert result.outputs["missing_scripts"] == [RESERVED_BUILD_SCRIPT]


def test_lint_needs_no_acquired_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Unlike inference, which scans upstream: a script can be checked from the
    # moment it is typed, before any source exists.
    _store_at(tmp_path, monkeypatch)
    upstream = tmp_path / "upstream"
    if upstream.is_dir():
        upstream.rmdir()
    _write_overlay(tmp_path, RESERVED_BUILD_SCRIPT, "set -eu\n")

    assert _run(_args("build")).status == "succeeded"


def test_an_experiment_target_without_a_name_is_a_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store_at(tmp_path, monkeypatch)
    result = _run(_args("experiment_run"))
    assert result.status == "failed"


def test_a_canceled_run_reports_canceled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _store_at(tmp_path, monkeypatch)
    _write_overlay(tmp_path, RESERVED_BUILD_SCRIPT, "set -eu\n")
    result = handler.handle_lint_scripts(_args("build"), log=_silent_log, is_canceled=lambda: True)
    assert result.status == "canceled"
