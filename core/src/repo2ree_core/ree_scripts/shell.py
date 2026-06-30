"""Formatting helpers for generated POSIX shell scripts."""

from __future__ import annotations

import re
from textwrap import dedent

_PLACEHOLDER_PATTERN = re.compile(r"@@[A-Z][A-Z0-9_]*@@")


def shell_text(script: str) -> str:
    """Normalize an indented Python string into left-aligned shell text."""
    return dedent(script).strip() + "\n"


def shell_single_quote(value: str) -> str:
    """Quote ``value`` for safe inclusion inside POSIX single quotes."""
    return "'" + value.replace("'", "'\\''") + "'"


def assert_no_placeholders(rendered: str, *, artifact: str) -> str:
    """Postcondition for generated text: all template placeholders were filled."""
    if _PLACEHOLDER_PATTERN.search(rendered):
        raise AssertionError(f"unresolved placeholder in generated {artifact}")
    return rendered
