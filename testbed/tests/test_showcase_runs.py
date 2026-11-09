"""The overview reads the newest finished run of each showcase tier that ran every test."""

import json
from pathlib import Path

from repo2ree_testbed.runs.showcase_runs import BROWSER_TIER, newest, showcase_runs
from repo2ree_testbed.showcases import api_tier, environments_in_use
from repo2ree_testbed.stack.environments import EnvironmentName


def run(runs: Path, name: str, tier: str, *, selected: tuple[str, ...] = ()) -> Path:
    directory = runs / name
    directory.mkdir(parents=True)
    record = {"tier": tier, "suite": "s.py", "build_revision": "a" * 40, "jobs": 1, "selected": selected, "tests": []}
    (directory / "run.json").write_text(json.dumps(record))
    return directory


def test_the_newest_run_of_a_tier_that_ran_every_test_is_read(tmp_path: Path) -> None:
    tier = api_tier(EnvironmentName.BARE)
    run(tmp_path, "a-20261101-000000", tier)
    kept = run(tmp_path, "a-20261102-000000", tier)
    run(tmp_path, "a-20261103-000000", tier, selected=("one",))
    run(tmp_path, "a-20261104-000000", api_tier(EnvironmentName.DOCKER))
    (tmp_path / "a-20261105-000000").mkdir()

    assert newest(tier, tmp_path) == kept


def test_every_showcase_tier_is_listed_with_its_run_or_none(tmp_path: Path) -> None:
    browser = run(tmp_path, "showcase-20261101-000000", BROWSER_TIER)

    tiers = showcase_runs(tmp_path).tiers

    assert [tier.tier for tier in tiers] == [BROWSER_TIER, *(api_tier(e) for e in environments_in_use())]
    assert tiers[0].run == str(browser)
    assert all(tier.run is None for tier in tiers[1:])
    assert {tier.environment for tier in tiers[1:]} == set(environments_in_use())
