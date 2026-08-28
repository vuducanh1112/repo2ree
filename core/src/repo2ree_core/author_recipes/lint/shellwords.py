"""Tokenize enough POSIX shell to ignore comments and distinguish operators."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

_OPERATORS = frozenset({"|", "||", "&", "&&", ";", ";;", "<", ">", ">>", "(", ")"})


@dataclass(frozen=True)
class Word:
    """One token and the line it was read on."""

    text: str
    line: int


@dataclass(frozen=True)
class ScriptWords:
    """A script's tokens, split into words and operators, comments dropped."""

    words: tuple[Word, ...]
    operators: tuple[Word, ...]

    def mentions(self, literal: str) -> Word | None:
        """Return the first word containing ``literal``."""
        if not literal:
            return None
        return next((word for word in self.words if literal in word.text), None)

    def operator(self, symbol: str) -> tuple[Word, ...]:
        """Every occurrence of one exact operator."""
        return tuple(word for word in self.operators if word.text == symbol)


def tokenize(source: str) -> ScriptWords:
    """Split source into words and operators, tolerating incomplete lines."""
    words: list[Word] = []
    operators: list[Word] = []
    for line_number, logical_line in _logical_lines(source):
        for token in _tokens(logical_line):
            entry = Word(text=token, line=line_number)
            if token in _OPERATORS:
                operators.append(entry)
            else:
                words.append(entry)
    return ScriptWords(words=tuple(words), operators=tuple(operators))


def _logical_lines(source: str) -> list[tuple[int, str]]:
    """Join backslash continuations and retain each logical line's start."""
    joined: list[tuple[int, str]] = []
    pending: list[str] = []
    start = 1
    for offset, raw in enumerate(source.splitlines(), start=1):
        if not pending:
            start = offset
        if raw.endswith("\\"):
            pending.append(raw[:-1])
            continue
        pending.append(raw)
        joined.append((start, " ".join(pending)))
        pending = []
    if pending:
        joined.append((start, " ".join(pending)))
    return joined


def _tokens(line: str) -> list[str]:
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    collected: list[str] = []
    while True:
        try:
            token = lexer.get_token()
        except ValueError:
            break
        if token is None:
            break
        collected.append(token)
    return collected
