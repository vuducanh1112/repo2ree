from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.bundle.repository_restore import verify_overlay


def test_a_loaded_ree_may_hold_its_scripts_in_its_overlay(tmp_path: Path) -> None:
    script = tmp_path / "overlay/ree-scripts/experiments/hello.verify.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n")
    verify_overlay(tmp_path)


def test_a_loaded_ree_with_anything_else_in_its_overlay_is_refused(tmp_path: Path) -> None:
    stray = tmp_path / "overlay/project/requirements-extra.txt"
    stray.parent.mkdir(parents=True)
    stray.write_text("requests==2.31.0\n")
    with pytest.raises(ValueError, match=r"project/requirements-extra\.txt"):
        verify_overlay(tmp_path)
