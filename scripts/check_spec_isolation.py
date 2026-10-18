#!/usr/bin/env python3
"""Refuse a commit that changes the behaviour specification and the implementation together.

The specification is the oracle the implementation is checked against. When one
change edits both, the rules can be bent to fit the code and the checker will
agree with whatever was written. Specify first, then implement against the
committed specification. The generated machines module, the checker, docs, and
tests may change with the specification; runtime source may not.

Deliberate exceptions: ``SKIP=spec-isolation git commit ...``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

SPEC = "specifications/behaviour/"
RUNTIME_SOURCES = (
    "api/src/",
    "core/src/",
    "supervisor/src/",
    "executor/src/",
    "workbench/src/",
    "provider/src/",
    "protocol/src/",
    "docker-support/src/",
    "gui/src/",
)
GENERATED = frozenset({"protocol/src/repo2ree_protocol/behaviour/machines.py"})


def conflicts(paths: Sequence[str]) -> tuple[list[str], list[str]]:
    """(specification paths, runtime paths) when both are present, else two empty lists."""
    specification = [path for path in paths if path.startswith(SPEC)]
    runtime = [path for path in paths if path.startswith(RUNTIME_SOURCES) and path not in GENERATED]
    return (specification, runtime) if specification and runtime else ([], [])


def main(argv: Sequence[str] | None = None) -> int:
    specification, runtime = conflicts(list(sys.argv[1:] if argv is None else argv))
    if not specification:
        return 0
    print("This commit changes the behaviour specification and runtime code together:", file=sys.stderr)
    for path in specification + runtime:
        print(f"  {path}", file=sys.stderr)
    print(
        "Commit the specification (with its generated module) first, then the implementation.\n"
        "For a deliberate exception: SKIP=spec-isolation git commit ...",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
