from pathlib import Path

import pytest

from repo2ree_repoview.diagrams import recipes as recipe_graph


def recipes() -> dict[str, recipe_graph.Recipe]:
    return recipe_graph.parse_recipes(
        {
            "recipes": {
                "leaf": {"attributes": [{"group": "Checks"}], "body": [["run"]], "dependencies": []},
                "helper": {
                    "attributes": ["private"],
                    "private": True,
                    "body": [["run"]],
                    "dependencies": [],
                },
                "aggregate": {
                    "attributes": [{"group": "Checks"}],
                    "body": [],
                    "dependencies": [{"recipe": "leaf"}, {"recipe": "helper"}],
                    "priors": 2,
                },
                "fix": {
                    "attributes": [{"group": "Formatting"}],
                    "body": [["fix"]],
                    "dependencies": [{"recipe": "format"}],
                    "priors": 0,
                },
                "format": {
                    "attributes": [{"group": "Formatting"}],
                    "body": [["format"]],
                    "dependencies": [],
                },
                "unrelated": {"attributes": [], "body": [["run"]], "dependencies": []},
            }
        }
    )


def test_edges_follow_execution_order() -> None:
    edges = recipe_graph.execution_edges(recipes())

    assert ("leaf", "aggregate", False) in edges
    assert ("helper", "aggregate", False) in edges
    assert ("fix", "format", True) in edges


def test_dot_places_sources_first_and_distinguishes_recipe_kinds() -> None:
    dot = recipe_graph.render_dot(recipes())

    assert "rankdir=LR" in dot
    assert '{ rank=source; "fix"; "helper"; "leaf"; "unrelated"; }' in dot
    assert '"aggregate" [label="aggregate"' in dot
    assert "penwidth=2.2" in dot
    assert 'style="rounded,filled,dashed"' in dot
    assert '"fix" -> "format" [style=dashed, label="after"' in dot


def test_root_selects_only_the_dependency_closure() -> None:
    dot = recipe_graph.render_dot(recipes(), root="aggregate")

    assert "rankdir=LR" in dot
    assert '"aggregate"' in dot
    assert '"leaf"' in dot
    assert '"helper"' in dot
    assert '"unrelated"' not in dot
    assert 'color="#0f766e"' in dot


def test_unknown_root_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown Just recipe: missing"):
        recipe_graph.render_dot(recipes(), root="missing")


def suite_recipes(**bodies: tuple[str, list[str], list[dict[str, object]]]) -> dict[str, recipe_graph.Recipe]:
    """Recipes each with a body, the paths it declares it runs, and its dependencies."""
    return recipe_graph.parse_recipes(
        {
            "recipes": {
                name: {
                    "attributes": [{"metadata": ["runs", *runs]}] if runs else [],
                    "body": [[body]],
                    "dependencies": dependencies,
                }
                for name, (body, runs, dependencies) in bodies.items()
            }
        }
    )


def project(tmp_path: Path) -> Path:
    (tmp_path / "gui/tests/e2e-instant").mkdir(parents=True)
    (tmp_path / "testbed/suites/system").mkdir(parents=True)
    (tmp_path / "gui/playwright.config.ts").write_text(
        '{\n      name: "e2e-gui-instant",\n      testDir: "./tests/e2e-instant",\n}\n'
    )
    return tmp_path


def test_what_a_recipe_runs_is_drawn_as_a_node_of_its_own() -> None:
    declared = suite_recipes(tier=("python run_system_suite.py", ["testbed/suites/system/"], []))
    assert declared["tier"].runs == ("testbed/suites/system",)
    dot = recipe_graph.render_dot(declared)
    assert '"runs:testbed/suites/system" [label="testbed/suites/system", shape=folder' in dot
    assert '"tier" -> "runs:testbed/suites/system" [style=dotted' in dot


def test_a_suite_a_recipe_names_must_be_declared(tmp_path: Path) -> None:
    root = project(tmp_path)
    declared = suite_recipes(
        by_path=("python -m e2e --script testbed/suites/system/run_system_suite.py", [], []),
        by_project=("playwright test --project=e2e-gui-instant", [], []),
        by_command=("python -m repo2ree_testbed api-showcase run --jobs 1", [], []),
        by_argument=("", [], [{"recipe": "_source-stack-playwright", "arguments": ["e2e-gui-instant", "1"]}]),
        listing=("python -m repo2ree_testbed api-showcase environments", [], []),
        covered=("python testbed/suites/system/run_system_suite.py", ["testbed/suites/system"], []),
        gone=("echo", ["testbed/suites/gone"], []),
    )
    declare = 'and does not declare it: [metadata("runs", "{}")]'
    assert recipe_graph.undeclared_runs(declared, root) == [
        "by_argument runs gui/tests/e2e-instant " + declare.format("gui/tests/e2e-instant"),
        "by_command runs testbed/suites/showcase " + declare.format("testbed/suites/showcase"),
        "by_path runs testbed/suites/system/run_system_suite.py " + declare.format("testbed/suites/system"),
        "by_project runs gui/tests/e2e-instant " + declare.format("gui/tests/e2e-instant"),
        "gone declares it runs testbed/suites/gone, which is not there",
    ]


def test_every_recipe_declares_what_it_runs() -> None:
    assert recipe_graph.undeclared_runs(recipe_graph.load_recipes()) == []
