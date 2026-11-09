"""Which run of each showcase tier the overview reads, the newest finished one that ran every test, and
each showcase's tests in those runs.

python -m repo2ree_testbed showcase-runs -o reports/exports/showcases.json
python -m repo2ree_testbed showcase-runs --list    # those runs' paths, one a line
"""

import argparse
import sys
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from repo2ree_testbed.artifacts import ROOT, run_dir
from repo2ree_testbed.records import RunRecord, read
from repo2ree_testbed.showcases import (
    FEATURES,
    FEATURES_ENVIRONMENT,
    GUI_SHOWCASES,
    GUI_SUITE,
    SHOWCASES,
    ShowcaseName,
    Workflow,
    api_test,
    api_tier,
    environments_in_use,
)
from repo2ree_testbed.stack.environments import EnvironmentName

# The browser showcases' tier, as its Playwright project names it.
BROWSER_TIER = "showcase"

Surface = Literal["api", "browser"]


class ShowcaseTier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: str
    surface: Surface
    # The machine its API showcases run on; None for the browser showcases, on the default stack.
    environment: EnvironmentName | None
    recipe: str
    # From the repository root; None when this clone has no finished run of it that ran every test.
    run: str | None


class ShowcaseTest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    surface: Surface
    # None for a feature's tests, which are of no one workflow.
    workflow: Workflow | None
    # The test file, from the repository root.
    file: str
    tier: str
    # The run it is read from, as its tier names it, and its name there; None when that run has no such test.
    run: str | None
    test: str | None


class Showcase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: Literal["showcase", "feature"]
    # The machine its API tests run on.
    environment: EnvironmentName | None
    tests: tuple[ShowcaseTest, ...]


class ShowcaseRuns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["repo2ree-showcase-runs/1"] = "repo2ree-showcase-runs/1"
    tiers: tuple[ShowcaseTier, ...]
    showcases: tuple[Showcase, ...]


def newest(tier: str, runs: Path) -> Path | None:
    """The newest run of ``tier`` that finished and ran every test its suite lists."""
    found = [
        record_path.parent
        for record_path in sorted(runs.glob("*/run.json"))
        if (record := read(RunRecord, record_path)) is not None and record.tier == tier and not record.selected
    ]
    return max(found, key=lambda run: run.name, default=None)


def named(run: Path | None) -> str | None:
    if run is None:
        return None
    return str(run.relative_to(ROOT)) if run.is_relative_to(ROOT) else str(run)


def api_file(test: str) -> str:
    """The file of a pytest node id."""
    return test.split("::", 1)[0]


def browser_file(test: str) -> str:
    """The spec file of a Playwright title path, from the repository root."""
    return str(Path("gui/tests") / test.split(" > ", 1)[0])


class _Found:
    """The tests of each tier's chosen run, by the file they are in."""

    def __init__(self, tiers: tuple[ShowcaseTier, ...]) -> None:
        self.runs = {tier.tier: tier.run for tier in tiers}
        self.files: dict[tuple[str, str], list[str]] = {}
        for tier in tiers:
            record = read(RunRecord, ROOT / tier.run / "run.json") if tier.run else None
            for test in record.tests if record else ():
                file = browser_file(test.name) if tier.surface == "browser" else api_file(test.name)
                self.files.setdefault((tier.tier, file), []).append(test.name)

    def tests(self, surface: Surface, workflow: Workflow | None, tier: str, file: str) -> list[ShowcaseTest]:
        run = self.runs.get(tier)
        found: list[str | None] = [*self.files.get((tier, file), [])] if run else []
        return [
            ShowcaseTest(surface=surface, workflow=workflow, file=file, tier=tier, run=run if test else None, test=test)
            for test in found or [None]
        ]


def from_root(path: Path) -> str:
    return str(path.relative_to(ROOT))


def showcases(found: _Found) -> tuple[Showcase, ...]:
    listed = []
    for name in ShowcaseName:
        environment = SHOWCASES[name].environment
        tests: list[ShowcaseTest] = []
        for workflow in get_args(Workflow):
            tests += found.tests("api", workflow, api_tier(environment), from_root(api_test(name, workflow)))
            if spec := GUI_SHOWCASES.get(name, {}).get(workflow):
                tests += found.tests("browser", workflow, BROWSER_TIER, from_root(GUI_SUITE / spec))
        listed.append(Showcase(name=name, kind="showcase", environment=environment, tests=tuple(tests)))
    for feature, files in FEATURES.items():
        tests = []
        if files.api:
            tests += found.tests("api", None, api_tier(FEATURES_ENVIRONMENT), from_root(files.api))
        if files.gui:
            tests += found.tests("browser", None, BROWSER_TIER, from_root(GUI_SUITE / files.gui))
        machine = FEATURES_ENVIRONMENT if files.api else None
        listed.append(Showcase(name=feature, kind="feature", environment=machine, tests=tuple(tests)))
    return tuple(listed)


def showcase_runs(runs: Path) -> ShowcaseRuns:
    browser = ShowcaseTier(
        tier=BROWSER_TIER,
        surface="browser",
        environment=None,
        recipe="just test-showcase",
        run=named(newest(BROWSER_TIER, runs)),
    )
    api = (
        ShowcaseTier(
            tier=api_tier(environment),
            surface="api",
            environment=environment,
            recipe=f"just api-showcase-on {environment}",
            run=named(newest(api_tier(environment), runs)),
        )
        for environment in environments_in_use()
    )
    tiers = (browser, *api)
    return ShowcaseRuns(tiers=tiers, showcases=showcases(_Found(tiers)))


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed showcase-runs", description=__doc__.split("\n\n")[0])
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("-o", "--output", type=Path, help="write the export here")
    output.add_argument("--list", action="store_true", help="print the runs' paths, one a line")
    args = parser.parse_args()
    chosen = showcase_runs(run_dir() / "e2e")
    if args.list:
        sys.stdout.write("".join(f"{tier.run}\n" for tier in chosen.tiers if tier.run))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(chosen.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
