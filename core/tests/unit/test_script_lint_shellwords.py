"""Reading a script as words: what the tokenizer sees, and what it refuses to guess.

Line numbers are load-bearing — an editor anchors every finding to one — so the
cases below are as much about *which line* a token is attributed to as about
which tokens appear at all.
"""

from __future__ import annotations

import pytest

from repo2ree_core.author_recipes.lint.shellwords import tokenize


def _words(source: str) -> list[tuple[str, int]]:
    return [(word.text, word.line) for word in tokenize(source).words]


def test_comments_are_not_words() -> None:
    assert _words("# docker run img\necho hi\n") == [("echo", 2), ("hi", 2)]


def test_a_shebang_is_a_comment_like_any_other() -> None:
    assert _words("#!/usr/bin/env sh\nset -eu\n") == [("set", 2), ("-eu", 2)]


def test_quotes_are_resolved_and_their_contents_kept_whole() -> None:
    assert _words('echo "a | b"\n') == [("echo", 1), ("a | b", 1)]


def test_every_token_on_a_line_is_attributed_to_that_line() -> None:
    # shlex.lineno reports where a token stopped being scanned, which is one
    # line late for whichever token ends a line — usually the interesting one.
    assert _words("set -eu\ndocker load\n") == [
        ("set", 1),
        ("-eu", 1),
        ("docker", 2),
        ("load", 2),
    ]


def test_a_continued_line_is_one_logical_line() -> None:
    source = "docker run --rm \\\n  -w /workspace \\\n  img main.py\n"
    assert _words(source) == [
        ("docker", 1),
        ("run", 1),
        ("--rm", 1),
        ("-w", 1),
        ("/workspace", 1),
        ("img", 1),
        ("main.py", 1),
    ]


def test_a_pipe_is_an_operator_and_an_or_is_a_different_one() -> None:
    words = tokenize("a | b\nc || d\n")
    assert [(w.text, w.line) for w in words.operator("|")] == [("|", 1)]
    assert [w.text for w in words.operator("||")] == ["||"]


def test_unbalanced_quoting_keeps_what_was_read_rather_than_raising() -> None:
    # Saying *why* a script will not parse belongs to the syntax tier. Here it
    # only means the later lines contribute fewer tokens.
    words = tokenize('echo ok\necho "unterminated\n')
    assert ("ok", 1) in [(w.text, w.line) for w in words.words]


@pytest.mark.parametrize("source", ["", "\n\n", "# nothing but a comment\n"])
def test_a_script_with_nothing_to_say_yields_nothing(source: str) -> None:
    words = tokenize(source)
    assert words.words == ()
    assert words.operators == ()


def test_mentions_finds_a_path_written_into_an_assignment() -> None:
    words = tokenize('RUNTIME_ARTIFACT="runtime.tar"\n')
    assert words.mentions("runtime.tar") is not None
    assert words.mentions("other.tar") is None


def test_mentions_ignores_a_path_that_appears_only_in_a_comment() -> None:
    words = tokenize("# writes runtime.tar eventually\ndocker build .\n")
    assert words.mentions("runtime.tar") is None


def test_the_empty_string_is_not_a_mention_of_everything() -> None:
    assert tokenize("echo hi\n").mentions("") is None
