#!/usr/bin/env python3
"""The exercise cases as a stack's client (``python -m repo2ree_testbed e2e --script``): each case on a machine of
its own, with no service on it, where the test runs ``ree`` itself."""

import sys
from pathlib import Path

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.stack.environments import EnvironmentName

# Debian with Python, all the instant project the cases author needs.
MACHINE = EnvironmentName.BARE

if __name__ == "__main__":
    sys.exit(run(Path(__file__).resolve().parent / "test_cases.py", machine=lambda node: MACHINE))
