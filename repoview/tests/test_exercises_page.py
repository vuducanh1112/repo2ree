from typing import Any

from repo2ree_repoview.overview.exports import Exercises, Move
from repo2ree_repoview.overview.pages.exercises import behaviour_label, case_slug, page_exercise, page_exercises

SEARCHED = "0dde2001bd088a93"
WRITTEN = "1f4f416e432bba33"
HELD = {"kind": "verdict", "rule": "evidence", "verdict": "held"}
SEALED = {
    "kind": "move",
    "aggregate": "Ree",
    "machine": "lifecycle",
    "part": "lifecycle",
    "operation": "seal_ree",
    "source": "draft",
    "target": "sealed",
}
SOURCE_SET = {
    "kind": "move",
    "aggregate": "Ree",
    "machine": "definition.source",
    "part": "field",
    "operation": "acquire_source",
    "source": "unset",
    "target": "set",
}
REFUSED = {"kind": "outcome", "command": "load-ree-bundle", "status": "failed", "category": "validation"}
UNSET = {**SOURCE_SET, "operation": "remove_source", "source": "set", "target": "unset"}


def _case(digest: str, origin: dict[str, Any], **parts: Any) -> dict[str, Any]:
    return {
        "digest": digest,
        "exercise": {
            "format": "repo2ree-exercise/1",
            "rees": ["author", "reviewer"],
            "steps": [
                {"ree": "author", "operation": "initialize_ree", "name": None},
                {"ree": "reviewer", "operation": "load_ree_bundle", "exported_by": "author", "corruption": "truncated"},
            ],
            "faults": [],
            "drifts": [{"before": 1, "ree": "author", "kind": "overlay", "change": "written"}],
        },
        "origin": origin,
        "expects": {"kind": "conforms"},
        "behaviours": {"spec_digest": "sha256:spec", "behaviours": [HELD, SEALED, SOURCE_SET, REFUSED]},
        "unique_behaviours": [SOURCE_SET, REFUSED],
        "coverage": None,
        "replay": None,
        **parts,
    }


def exercises(**cases: Any) -> Exercises:
    replay = {
        "workdir": "test-artifacts/exercises/run/replay/x",
        "when": "2026-11-23T12:00:00+00:00",
        "spec_digest": "sha256:spec",
        "problems": [],
        "behaviours": [HELD, SEALED, SOURCE_SET, REFUSED],
        "steps": [
            {
                "step": 0,
                "ree": "author",
                "operation": "initialize_ree",
                "words": ["initialize-ree"],
                "exit": 0,
                "status": "succeeded",
                "failure": None,
                "scope": ".",
                "commit": "aaaaaaaa11",
                "changed": True,
            },
            {
                "step": 1,
                "ree": "reviewer",
                "operation": "load_ree_bundle",
                "words": ["load-ree-bundle"],
                "exit": 2,
                "status": "failed",
                "failure": "not a bundle",
                "scope": None,
                "commit": None,
                "changed": None,
            },
        ],
        "session": "test-artifacts/exercises/run/replay/x/session/index.html",
    }
    campaign = {
        "run": "run-1",
        "search": "spec-cov",
        "settings": {"examples": 50, "steps": 20, "keep": 1000, "least": 1, "hours": 4.0, "workers": 5},
        "commit": "773ea50782f05cad",
        "dirty": False,
        "machine": "vm",
        "started": "2026-11-23T18:30:00+00:00",
        "ended": "2026-11-23T22:40:00+00:00",
        "rounds": 120,
        "rounds_found": 6,
        "unconfirmed": 1,
        "kept": [
            {
                "case": SEARCHED,
                "kept_for": {"kind": "new_behaviours", "behaviours": [HELD]},
                "steps": 2,
                "worker": 3,
            },
            {"case": "0123456789abcdef", "kept_for": {"kind": "showed_problems"}, "steps": 4, "worker": 1},
        ],
        "exit": 0,
    }
    return Exercises.model_validate(
        {
            "format": "repo2ree-exercises/1",
            "campaigns": [campaign],
            "declared": [HELD, SEALED, UNSET],
            "cases": [
                _case(
                    SEARCHED,
                    {
                        "kind": "searched",
                        "search": "spec-cov",
                        "run": "run-1",
                        "kept_for": {"kind": "new_behaviours", "behaviours": [HELD]},
                    },
                    replay=replay,
                ),
                _case(WRITTEN, {"kind": "hand_written"}),
            ],
            **cases,
        }
    )


def test_the_exercises_page_lists_the_campaigns_and_every_case_linked_to_its_page() -> None:
    body = page_exercises(exercises()).body

    assert 'id="campaign-run-1"' in body
    assert "4 h 10 min" in body
    assert f'href="{case_slug(SEARCHED)}.html"' in body
    assert f'href="{case_slug(WRITTEN)}.html"' in body
    assert 'href="exercises.html#campaign-run-1"' in body
    assert "hand-written" in body
    assert '<code>0123456789abcdef</code> <span class="muted">removed</span>' in body
    assert 'href="exercises/0123456789abcdef.html"' not in body


def test_without_campaigns_the_page_says_how_to_record_one() -> None:
    body = page_exercises(exercises(campaigns=[])).body

    assert "None recorded." in body
    assert "campaign-run-1" not in body


def test_a_case_page_draws_its_replay_links_its_session_and_shows_what_it_reached() -> None:
    page = page_exercise(exercises().cases[0], session=True)

    assert page.slug == case_slug(SEARCHED)
    assert '<svg class="seq"' in page.body
    assert "bundle (truncated)" in page.body
    assert "drift: overlay" in page.body
    assert "load_ree_bundle → failed" in page.body
    assert "evidence.html?from=exercises#evidence/exercises/0dde2001bd088a93/session/index.html" in page.body
    assert "only here" in page.body
    assert "Not measured." in page.body


def test_a_case_without_a_replay_draws_the_exercise_as_written() -> None:
    page = page_exercise(exercises().cases[1])

    assert "session/index.html" not in page.body
    assert '<svg class="seq"' in page.body
    assert "initialize_ree</text>" in page.body


def test_the_exercises_page_shows_what_is_declared_covered_each_behaviour_in_words_and_what_no_case_covers() -> None:
    body = page_exercises(exercises()).body

    assert "2 of the 3 declared behaviours covered, and 2 more that nothing declares." in body
    assert "<code>ree load-ree-bundle</code> failed (validation)" in body
    assert "<code>seal_ree</code> takes the REE from draft to sealed" in body
    assert "<code>acquire_source</code> sets the REE's <code>definition.source</code>" in body
    assert "Declared, covered by no case (1)" in body
    assert "<code>remove_source</code> clears the REE's <code>definition.source</code>" in body


def test_a_case_page_lists_its_behaviours_marking_those_only_it_covers() -> None:
    body = page_exercise(exercises().cases[0], session=True).body

    assert body.count("<li>") >= 4
    assert body.count('<span class="ex">only here</span>') == 2


def test_a_change_no_operation_made_reads_as_one_outside_ree() -> None:
    outside = Move.model_validate({**SOURCE_SET, "operation": "(between operations)", "source": "set"})

    assert behaviour_label(outside) == "a change outside ree changes the REE's <code>definition.source</code>"
