"""Reading ShellCheck's output, against recorded documents rather than a binary.

The mapping is what these fix: which severity a level becomes, that the codes
stay in ShellCheck's own namespace, and that a document this does not recognize
produces no claims at all.
"""

from __future__ import annotations

import json

import pytest

from repo2ree_core.author_recipes.lint.shellcheck_json import parse_json1

# One real `shellcheck --shell sh --format=json1` document, trimmed to the
# fields the parser reads plus the `fix` block it deliberately ignores.
_REAL_OUTPUT = json.dumps(
    {
        "comments": [
            {
                "file": "-",
                "line": 3,
                "endLine": 3,
                "column": 9,
                "endColumn": 13,
                "level": "info",
                "code": 2086,
                "message": "Double quote to prevent globbing and word splitting.",
                "fix": {"replacements": []},
            }
        ]
    }
)


def test_a_comment_becomes_a_finding_in_shellchecks_own_namespace() -> None:
    (finding,) = parse_json1(_REAL_OUTPUT, path="ree-scripts/build_script.sh")
    assert finding.code == "shellcheck:SC2086"
    assert finding.tier == "shell"
    assert finding.line == 3
    assert finding.column == 9
    assert finding.path == "ree-scripts/build_script.sh"


def test_shellcheck_never_blocks() -> None:
    # Its vocabulary is not ours: it reports nothing for the pitfalls that
    # matter here, and its advice is occasionally the bug. It advises only.
    (finding,) = parse_json1(_REAL_OUTPUT, path="x.sh")
    assert finding.blocking is False


@pytest.mark.parametrize(
    ("level", "severity"),
    [("error", "error"), ("warning", "warning"), ("info", "info"), ("style", "info")],
)
def test_levels_map_onto_our_severities(level: str, severity: str) -> None:
    payload = json.dumps({"comments": [{"level": level, "code": 1000, "message": "m"}]})
    (finding,) = parse_json1(payload, path="x.sh")
    assert finding.severity == severity


def test_an_unknown_level_is_read_as_the_mildest_thing() -> None:
    payload = json.dumps({"comments": [{"level": "verbose", "code": 1000, "message": "m"}]})
    (finding,) = parse_json1(payload, path="x.sh")
    assert finding.severity == "info"


def test_a_clean_script_produces_nothing() -> None:
    assert parse_json1(json.dumps({"comments": []}), path="x.sh") == ()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("", id="empty"),
        pytest.param("not json at all", id="unparseable"),
        pytest.param("[]", id="not an object"),
        pytest.param('{"comments": "nope"}', id="comments is not a list"),
        pytest.param('{"comments": [{"code": 1, "message": 5}]}', id="a message that is not text"),
        pytest.param('{"comments": [{"message": "no code"}]}', id="a comment with no code"),
    ],
)
def test_output_this_does_not_recognize_yields_no_claims(payload: str) -> None:
    # A shape we cannot read means a ShellCheck the caller should treat as
    # unavailable — never a script to invent findings about.
    assert parse_json1(payload, path="x.sh") == ()
