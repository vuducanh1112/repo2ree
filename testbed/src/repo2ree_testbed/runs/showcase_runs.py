import argparse
import sys
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict

from repo2ree_testbed.artifacts import ROOT, run_dir
from repo2ree_testbed.records import RunRecord, read
from repo2ree_testbed.showcases import (
    API_TIER,
    CLI_TIER,
    FEATURES,
    FEATURES_ENVIRONMENT,
    GUI_SHOWCASES,
    GUI_SUITE,
    REAL_WORLD,
    REAL_WORLD_TIER,
    SHOWCASES,
    ShowcaseName,
    Workflow,
    api_test,
    environments_in_use,
    gui_machines,
    real_world_test,
)
from repo2ree_testbed.stack.environments import EnvironmentName

BROWSER_TIER = "showcase"

Surface = Literal["api", "cli", "browser"]
Selection = Literal["whole", "each_test"]


class ShowcaseTier(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: str
    surface: Surface
    environments: tuple[EnvironmentName, ...]
    recipe: str
    selection: Selection
    run: str | None


class ShowcaseTest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    surface: Surface
    workflow: Workflow | None
    file: str
    tier: str
    run: str | None
    test: str | None


class Showcase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: Literal["showcase", "feature", "real_world"]
    environment: EnvironmentName | None
    tests: tuple[ShowcaseTest, ...]


class ShowcaseRuns(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal["repo2ree-showcase-runs/2"] = "repo2ree-showcase-runs/2"
    tiers: tuple[ShowcaseTier, ...]
    showcases: tuple[Showcase, ...]


def runs_of(tier: str, runs: Path, *, whole: bool) -> list[Path]:
    found = [
        record_path.parent
        for record_path in runs.glob("*/run.json")
        if (record := read(RunRecord, record_path)) is not None
        and record.tier == tier
        and not (whole and record.selected)
    ]
    return sorted(found, key=lambda run: run.name)


def newest(tier: str, runs: Path) -> Path | None:
    return next(reversed(runs_of(tier, runs, whole=True)), None)


def relative(run: Path) -> str:
    return str(run.relative_to(ROOT)) if run.is_relative_to(ROOT) else str(run)


def named(run: Path | None) -> str | None:
    return None if run is None else relative(run)


def api_file(test: str) -> str:
    return test.split("::", 1)[0]


def browser_file(test: str) -> str:
    return str(Path("gui/tests") / test.split(" > ", 1)[0])


class _Found:
    def __init__(self, tiers: tuple[ShowcaseTier, ...], runs: Path) -> None:
        self.files: dict[tuple[str, str], tuple[str, list[str]]] = {}
        for tier in tiers:
            read_from = runs_of(tier.tier, runs, whole=False) if tier.selection == "each_test" else []
            for run in [ROOT / tier.run] if tier.run else read_from:
                record = read(RunRecord, run / "run.json")
                ran: dict[str, list[str]] = {}
                for test in record.tests if record else ():
                    file = browser_file(test.name) if tier.surface == "browser" else api_file(test.name)
                    ran.setdefault(file, []).append(test.name)
                for file, names in ran.items():
                    self.files[(tier.tier, file)] = (relative(run), names)

    def tests(self, surface: Surface, workflow: Workflow | None, tier: str, file: str) -> list[ShowcaseTest]:
        run, names = self.files.get((tier, file), (None, []))
        found: list[str | None] = [*names]
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
            tests += found.tests("api", workflow, API_TIER, from_root(api_test(name, workflow)))
            tests += found.tests("cli", workflow, CLI_TIER, from_root(api_test(name, workflow)))
            if spec := GUI_SHOWCASES.get(name, {}).get(workflow):
                tests += found.tests("browser", workflow, BROWSER_TIER, from_root(GUI_SUITE / spec))
        listed.append(Showcase(name=name, kind="showcase", environment=environment, tests=tuple(tests)))
    for feature, files in FEATURES.items():
        tests = []
        if files.api:
            tests += found.tests("api", None, API_TIER, from_root(files.api))
            tests += found.tests("cli", None, CLI_TIER, from_root(files.api))
        if files.gui:
            tests += found.tests("browser", None, BROWSER_TIER, from_root(GUI_SUITE / files.gui))
        machine = FEATURES_ENVIRONMENT if files.api else None
        listed.append(Showcase(name=feature, kind="feature", environment=machine, tests=tuple(tests)))
    for project, environment in REAL_WORLD.items():
        tests = found.tests("cli", None, REAL_WORLD_TIER, from_root(real_world_test(project)))
        listed.append(Showcase(name=project, kind="real_world", environment=environment, tests=tuple(tests)))
    return tuple(listed)


def browser_machines() -> set[EnvironmentName]:
    return {machine for spec, machine in gui_machines().items() if spec.is_relative_to(GUI_SUITE)}


def showcase_runs(runs: Path) -> ShowcaseRuns:
    browser = ShowcaseTier(
        tier=BROWSER_TIER,
        surface="browser",
        environments=tuple(environment for environment in EnvironmentName if environment in browser_machines()),
        recipe="just test-showcase",
        selection="whole",
        run=named(newest(BROWSER_TIER, runs)),
    )
    api = ShowcaseTier(
        tier=API_TIER,
        surface="api",
        environments=environments_in_use(),
        recipe=f"just test-{API_TIER}",
        selection="whole",
        run=named(newest(API_TIER, runs)),
    )
    cli = ShowcaseTier(
        tier=CLI_TIER,
        surface="cli",
        environments=environments_in_use(),
        recipe=f"just test-{CLI_TIER}",
        selection="whole",
        run=named(newest(CLI_TIER, runs)),
    )
    real_world = ShowcaseTier(
        tier=REAL_WORLD_TIER,
        surface="cli",
        environments=tuple(environment for environment in EnvironmentName if environment in REAL_WORLD.values()),
        recipe=f"just test-{REAL_WORLD_TIER}",
        selection="each_test",
        run=None,
    )
    tiers = (browser, api, cli, real_world)
    return ShowcaseRuns(tiers=tiers, showcases=showcases(_Found(tiers, runs)))


def main() -> int:
    parser = argparse.ArgumentParser(prog="repo2ree_testbed showcase-runs")
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
