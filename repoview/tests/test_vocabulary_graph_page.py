from __future__ import annotations

from repo2ree_repoview.overview.exports import VocabularyGraph
from repo2ree_repoview.overview.pages.vocabulary_graph import page_vocabulary_graph


def graph(problems: tuple[str, ...] = ()) -> VocabularyGraph:
    return VocabularyGraph.model_validate(
        {
            "format": "repo2ree-vocabulary/1",
            "roots": ["operations"],
            "vocabularies": [
                {
                    "name": "operations",
                    "origin": "spec",
                    "summary": "",
                    "where": "spec",
                    "names": ["build"],
                    "anchored": True,
                },
                {
                    "name": "steps",
                    "origin": "contract",
                    "summary": "The steps.",
                    "where": "cli:/x",
                    "names": ["build", "metadata"],
                    "anchored": True,
                },
                {
                    "name": "loose",
                    "origin": "source",
                    "summary": "",
                    "where": "a.py::X",
                    "names": ["build"],
                    "anchored": False,
                },
            ],
            "edges": [
                {
                    "target": "steps",
                    "relation": "within",
                    "sources": ["operations"],
                    "extras": ["metadata"],
                    "problems": list(problems),
                },
            ],
            "exceptions": [{"site": "x.py::Y", "reason": "an output's fields"}],
            "problems": list(problems),
        }
    )


def test_the_page_draws_every_vocabulary_and_lists_its_exceptions() -> None:
    page = page_vocabulary_graph(graph())
    assert page.slug == "vocabulary-graph"
    assert "<svg" in page.body
    assert 'id="vocabulary-steps"' in page.body
    assert "within <code>operations</code>" in page.body
    assert "+metadata" in page.body
    assert "an output&#x27;s fields" in page.body
    assert page.teaser == "3 vocabularies, 1 edges: 0 failing edges, 1 unanchored"


def test_a_failing_edge_and_what_the_check_found_are_on_the_page() -> None:
    page = page_vocabulary_graph(graph(("steps within operations: [seal] is in no source",)))
    assert "! steps within operations: [seal] is in no source" in page.body
    assert page.teaser.startswith("3 vocabularies, 1 edges: 1 failing edges, 1 unanchored")
