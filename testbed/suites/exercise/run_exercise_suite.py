#!/usr/bin/env python3
import sys
from pathlib import Path

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.stack.environments import EnvironmentName

MACHINE = EnvironmentName.BARE

if __name__ == "__main__":
    sys.exit(run(Path(__file__).resolve().parent / "test_cases.py", machine=lambda node: MACHINE))
