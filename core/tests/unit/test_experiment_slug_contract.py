"""The experiment-name slug rule, pinned against the cross-language fixture.

The GUI derives the same reserved script path locally (see
``gui/src/shell/data/scriptTemplates/paths.test.ts``), so the rule has two
implementations. Both assert against ``contracts/experiment-slugs.json``: if
either side changes how a name becomes a slug, one of the two suites fails
instead of the two silently disagreeing about where a script lives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from repo2ree_core.reserved_paths import (
    RESERVED_EXPERIMENT_SCRIPT_DIR,
    experiment_run_script_path,
    experiment_slug,
    experiment_verify_script_path,
)

_FIXTURE = Path(__file__).resolve().parents[3] / "contracts" / "experiment-slugs.json"
_CASES = json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _CASES, ids=[repr(case["name"]) for case in _CASES])
def test_experiment_slug_matches_the_shared_fixture(case: dict[str, str]) -> None:
    assert experiment_slug(case["name"]) == case["slug"]


@pytest.mark.parametrize("case", _CASES, ids=[repr(case["name"]) for case in _CASES])
def test_reserved_script_paths_are_built_from_the_slug(case: dict[str, str]) -> None:
    slug = case["slug"]
    assert experiment_run_script_path(case["name"]) == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{slug}.sh"
    assert experiment_verify_script_path(case["name"]) == f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{slug}.verify.sh"
