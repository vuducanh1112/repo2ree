import json
import os
import time
from pathlib import Path

from repo2ree_testbed.runs import prune

NOW = time.time()
OLD = NOW - 30 * 24 * 3600


def per_test_run(
    root: Path, name: str, *, outcome: str = "passed", behaviour: str = "passed", done: bool = True
) -> Path:
    run = root / name
    run.mkdir(parents=True)
    if done:
        test = {"name": "t", "outcome": outcome, "behaviour": behaviour}
        (run / "run.json").write_text(json.dumps({"tests": [test]}))
    os.utime(run, (OLD, OLD))
    return run


def names(paths: list[Path]) -> set[str]:
    return {path.name for path in paths}


def test_per_test_runs_keep_the_newest_the_newest_problem_the_receipt_and_runs_in_progress(tmp_path: Path) -> None:
    root = tmp_path / "e2e"
    for day in range(1, 9):
        per_test_run(root, f"e2e-system-2026100{day}-120000")
    per_test_run(root, "e2e-system-20261001-130000", outcome="failed")  # older problem, shadowed by a newer one
    per_test_run(root, "e2e-system-20261002-130000", behaviour="violated")
    per_test_run(root, "e2e-system-20261003-090000", done=False)  # crashed long ago: no run.json, old
    running = per_test_run(root, "e2e-system-20261009-120000", done=False)
    os.utime(running, (NOW, NOW))
    per_test_run(root, "e2e-gui-instant-20261001-120000")

    plan = prune.plan_per_test_runs(root, 2, {(root / "e2e-system-20261001-120000").resolve()}, NOW)

    assert names(plan.keep) == {
        "e2e-system-20261009-120000",  # in progress
        "e2e-system-20261008-120000",
        "e2e-system-20261007-120000",  # the newest two finished runs, besides the one in progress
        "e2e-system-20261002-130000",  # the newest problem: passed, but behaviour violated
        "e2e-system-20261001-120000",  # named by the behaviour receipt
        "e2e-gui-instant-20261001-120000",  # tiers are counted apart
    }
    assert "e2e-system-20261003-090000" in names(plan.remove)
    assert "e2e-system-20261001-130000" in names(plan.remove)


def test_an_expected_failure_is_not_a_problem() -> None:
    assert not prune.had_problem(Path("/nonexistent"))


def test_suite_runs_keep_the_newest_per_tier_and_anything_recent(tmp_path: Path) -> None:
    for index in range(4):
        for folder in ("recordings", "archives"):
            path = tmp_path / folder / f"e2e-demo-gui-{index:032x}"
            path.mkdir(parents=True)
            stamp = OLD + index
            os.utime(path, (stamp, stamp))
    recent = tmp_path / "recordings" / f"e2e-e2e-system-{'f' * 32}"
    recent.mkdir()
    (tmp_path / "recordings" / "unrelated").mkdir()

    plan = prune.plan_suite_runs(tmp_path, 2, NOW)

    assert {path.relative_to(tmp_path).as_posix() for path in plan.remove} == {
        f"{folder}/e2e-demo-gui-{index:032x}" for folder in ("recordings", "archives") for index in (0, 1)
    }
    assert recent in plan.keep


def test_only_stale_control_state_is_removed(tmp_path: Path) -> None:
    stale = tmp_path / "state/control/e2e-a"
    fresh = tmp_path / "state/control/e2e-b"
    for path in (stale, fresh):
        path.mkdir(parents=True)
    os.utime(stale, (OLD, OLD))
    assert prune.plan_control_state(tmp_path, NOW).remove == [stale]
    assert prune.plan_control_state(tmp_path / "missing", NOW).remove == []
