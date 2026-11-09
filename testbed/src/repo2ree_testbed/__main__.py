"""``python -m repo2ree_testbed <command> [args]``: one entry point, so recipes do not name modules."""

from __future__ import annotations

import runpy
import sys

COMMANDS = {
    "e2e": "repo2ree_testbed.runs.e2e",
    "environment": "repo2ree_testbed.runs.environment",
    "images": "repo2ree_testbed.stack.images",
    "image-suite": "repo2ree_testbed.runs.image_suite",
    "workbench-cleanup": "repo2ree_testbed.stack.workbench_cleanup",
    "assess": "repo2ree_testbed.runs.assess",
    "visualize": "repo2ree_testbed.runs.visualize",
    "prune": "repo2ree_testbed.runs.prune",
    "coverage": "repo2ree_testbed.python_coverage",
    "machine": "repo2ree_testbed.runs.machine",
    "record": "repo2ree_testbed.runs.record",
    "api-showcase": "repo2ree_testbed.runs.api_showcase",
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(f"usage: python -m repo2ree_testbed {{{','.join(COMMANDS)}}} [args]")
    command = sys.argv.pop(1)
    sys.argv[0] = f"repo2ree_testbed {command}"
    runpy.run_module(COMMANDS[command], run_name="__main__")


if __name__ == "__main__":
    main()
