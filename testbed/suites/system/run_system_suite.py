#!/usr/bin/env python3
"""The system suite as a stack's client (``python -m repo2ree_testbed e2e --script``).

Its Docker tests run on a machine with a Docker daemon of its own, which sees the paths their scripts do; the
others beside the stack.
"""

import sys
from pathlib import Path

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.stack.environments import EnvironmentName

DOCKER_TESTS = "testbed/suites/system/test_docker.py::"


def machine_of(node: str) -> str:
    return EnvironmentName.DOCKER if node.startswith(DOCKER_TESTS) else ""


if __name__ == "__main__":
    sys.exit(run(Path(__file__).resolve().parent, machine=machine_of))
