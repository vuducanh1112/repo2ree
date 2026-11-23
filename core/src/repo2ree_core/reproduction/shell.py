from __future__ import annotations

import re
from textwrap import dedent

_PLACEHOLDER_PATTERN = re.compile(r"@@[A-Z][A-Z0-9_]*@@")


def shell_text(script: str) -> str:
    return dedent(script).strip() + "\n"


def shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def assert_no_placeholders(rendered: str, *, artifact: str) -> str:
    if _PLACEHOLDER_PATTERN.search(rendered):
        raise AssertionError(f"unresolved placeholder in generated {artifact}")
    return rendered
