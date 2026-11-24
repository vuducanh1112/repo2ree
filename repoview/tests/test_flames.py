from repo2ree_repoview.diagrams.recipes import Dependency, Recipe
from repo2ree_repoview.overview.flames import flame_graph
from repo2ree_repoview.overview.timings import Completed, End, Invocation, Start


def recipe(name: str, *dependencies: str) -> Recipe:
    return Recipe(name, "", False, True, tuple(Dependency(dependency) for dependency in dependencies))


RECIPES = {
    "gate": recipe("gate", "check", "tests"),
    "check": recipe("check", "lint"),
    "tests": recipe("tests", "fast", "slow", "lint"),
    "lint": recipe("lint"),
    "fast": recipe("fast"),
    "slow": recipe("slow"),
}


def run(*recipes: tuple[str, float]) -> Invocation:
    start = Start.model_validate(
        {
            "kind": "start",
            "schema": "repo2ree-just-timing/1",
            "invocation": "i",
            "argv": ["gate"],
            "started": "2026-11-24T10:00:00Z",
        }
    )
    done = tuple(Completed(kind="recipe", recipe=name, seconds=seconds) for name, seconds in recipes)
    return Invocation(start, done, End(kind="end", exit=0, seconds=40))


GATE = run(("lint", 2), ("check", 0), ("fast", 10), ("slow", 30), ("tests", 0), ("gate", 1))


def test_a_flamegraph_is_the_work_per_run_each_recipe_and_what_it_needs_does() -> None:
    frames = {frame.path: frame for frame in flame_graph([GATE, GATE], RECIPES)}

    assert frames[("gate",)].cost == 43.0
    assert frames[("gate", "check", "lint")].cost == 2.0
    assert ("gate", "tests", "lint") not in frames
    assert frames[("gate", "tests")].cost == 40.0
    assert frames[("gate", "tests", "slow")].start < frames[("gate", "tests", "fast")].start
