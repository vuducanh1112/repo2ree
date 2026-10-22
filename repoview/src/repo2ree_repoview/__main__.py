"""``python -m repo2ree_repoview <command> [args]``: one entry point, so recipes do not name modules."""

from __future__ import annotations

import runpy
import sys

COMMANDS = {
    "overview": "repo2ree_repoview.overview.build",
    "architecture": "repo2ree_repoview.diagrams.architecture",
    "evidence": "repo2ree_repoview.diagrams.evidence",
    "recipes": "repo2ree_repoview.diagrams.recipes",
    "stamp": "repo2ree_repoview.stamp",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(f"usage: python -m repo2ree_repoview {{{','.join(COMMANDS)}}} [args]")
    command = sys.argv.pop(1)
    sys.argv[0] = f"repo2ree_repoview {command}"
    runpy.run_module(COMMANDS[command], run_name="__main__")


if __name__ == "__main__":
    main()
