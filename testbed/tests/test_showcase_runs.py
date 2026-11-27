import json
from pathlib import Path

from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.runs.showcase_runs import BROWSER_TIER, newest, showcase_runs
from repo2ree_testbed.showcases import (
    API_TIER,
    CLI_TIER,
    REAL_WORLD,
    REAL_WORLD_TIER,
    ProjectName,
    environments_in_use,
    real_world_test,
)
from repo2ree_testbed.stack.environments import EnvironmentName


def run(runs: Path, name: str, tier: str, *, selected: tuple[str, ...] = (), tests: tuple[str, ...] = ()) -> Path:
    directory = runs / name
    directory.mkdir(parents=True)
    ran = [
        {
            "name": test,
            "selection": [],
            "outcome": "passed",
            "reason": "",
            "exit_code": 0,
            "started": 0.0,
            "finished": 1.0,
            "rees": [],
            "phases": {},
            "directory": f"tests/{index}",
        }
        for index, test in enumerate(tests)
    ]
    record = {"tier": tier, "suite": "s.py", "build_revision": "a" * 40, "jobs": 1, "selected": selected, "tests": ran}
    (directory / "run.json").write_text(json.dumps(record))
    return directory


def test_the_newest_run_of_a_tier_that_ran_every_test_is_read(tmp_path: Path) -> None:
    run(tmp_path, "a-20261101-000000", API_TIER)
    kept = run(tmp_path, "a-20261102-000000", API_TIER)
    run(tmp_path, "a-20261103-000000", API_TIER, selected=("one",))
    run(tmp_path, "a-20261104-000000", BROWSER_TIER)
    (tmp_path / "a-20261105-000000").mkdir()

    assert newest(API_TIER, tmp_path) == kept


def test_every_showcase_tier_is_listed_with_its_run_or_none(tmp_path: Path) -> None:
    browser = run(tmp_path, "showcase-20261101-000000", BROWSER_TIER)

    tiers = showcase_runs(tmp_path).tiers

    assert [tier.tier for tier in tiers] == [BROWSER_TIER, API_TIER, CLI_TIER, REAL_WORLD_TIER]
    assert [tier.surface for tier in tiers] == ["browser", "api", "cli", "cli"]
    assert [tier.selection for tier in tiers] == ["whole", "whole", "whole", "each_test"]
    assert tiers[0].run == str(browser)
    assert tiers[1].run is tiers[2].run is tiers[3].run is None
    assert tiers[0].environments == (EnvironmentName.BARE, EnvironmentName.DOCKER)
    assert tiers[1].environments == tiers[2].environments == environments_in_use()


def test_each_real_world_showcase_names_the_newest_run_that_ran_it_selected_or_not(tmp_path: Path) -> None:
    def node(project: ProjectName) -> str:
        return f"{real_world_test(project).relative_to(ROOT)}::test"

    dev, camelina = node(ProjectName.REPO2REE_DEV), node(ProjectName.TRR341_DROUGHT_CAMELINA)
    run(tmp_path, "showcase-real-world-20261101-000000", REAL_WORLD_TIER, tests=(dev, camelina))
    newer = run(tmp_path, "showcase-real-world-20261102-000000", REAL_WORLD_TIER, selected=("dev",), tests=(dev,))

    chosen = showcase_runs(tmp_path)
    tests = {showcase.name: showcase.tests for showcase in chosen.showcases if showcase.kind == "real_world"}

    assert set(tests) == {str(project) for project in REAL_WORLD}
    assert [(test.run, test.test, test.workflow) for test in tests[ProjectName.REPO2REE_DEV]] == [
        (str(newer), dev, None)
    ]
    [ran] = tests[ProjectName.TRR341_DROUGHT_CAMELINA]
    assert (Path(str(ran.run)).name, ran.test) == ("showcase-real-world-20261101-000000", camelina)
    [unrun] = tests[ProjectName.HEAT_SUICIDE_PROJECTION]
    assert (unrun.run, unrun.test, unrun.tier) == (None, None, REAL_WORLD_TIER)
