import pytest
from scripts.diagrams import just_graph


def recipes() -> dict[str, just_graph.Recipe]:
    return just_graph.parse_recipes(
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
    edges = just_graph.execution_edges(recipes())

    assert ("leaf", "aggregate", False) in edges
    assert ("helper", "aggregate", False) in edges
    assert ("fix", "format", True) in edges


def test_dot_places_sources_first_and_distinguishes_recipe_kinds() -> None:
    dot = just_graph.render_dot(recipes())

    assert "rankdir=LR" in dot
    assert '{ rank=source; "fix"; "helper"; "leaf"; "unrelated"; }' in dot
    assert '"aggregate" [label="aggregate"' in dot
    assert "penwidth=2.2" in dot
    assert 'style="rounded,filled,dashed"' in dot
    assert '"fix" -> "format" [style=dashed, label="after"' in dot


def test_root_selects_only_the_dependency_closure() -> None:
    dot = just_graph.render_dot(recipes(), root="aggregate")

    assert "rankdir=LR" in dot
    assert '"aggregate"' in dot
    assert '"leaf"' in dot
    assert '"helper"' in dot
    assert '"unrelated"' not in dot
    assert 'color="#0f766e"' in dot


def test_unknown_root_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown Just recipe: missing"):
        just_graph.render_dot(recipes(), root="missing")
