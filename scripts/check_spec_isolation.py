#!/usr/bin/env python3
"""Refuse a commit that changes the behaviour oracle and the implementation together.

The oracle is the specification and the checker that applies it, with the
checker's tests (among them the list of edges no scenario exercises). When one
change edits the oracle and the code it judges, the rules or their reading can
be bent to fit the code, and the checker will agree with whatever was written.
Change the oracle first, then implement against it as committed. The generated
machines module belongs to the specification; runtime source may not join it.

Deliberate exceptions: ``SKIP=spec-isolation git commit ...``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

SPEC = "specifications/behaviour/"
# The checker and its tests judge the runtime as the specification does.
ORACLE = (SPEC, "conformance/")
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
    """(oracle paths, runtime paths) when both are present, else two empty lists."""
    oracle = [path for path in paths if path.startswith(ORACLE)]
    runtime = [path for path in paths if path.startswith(RUNTIME_SOURCES) and path not in GENERATED]
    return (oracle, runtime) if oracle and runtime else ([], [])


def main(argv: Sequence[str] | None = None) -> int:
    oracle, runtime = conflicts(list(sys.argv[1:] if argv is None else argv))
    if not oracle:
        return 0
    print("This commit changes the behaviour oracle (spec or checker) and runtime code together:", file=sys.stderr)
    for path in oracle + runtime:
        print(f"  {path}", file=sys.stderr)
    print(
        "Commit the oracle (specification, its generated module, the checker) first, then the implementation.\n"
        "For a deliberate exception: SKIP=spec-isolation git commit ...",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
