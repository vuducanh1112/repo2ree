#!/usr/bin/env python3
"""The API showcases, as a stack's client (``python -m repo2ree_testbed e2e --script``): each test on its machine."""

import sys

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.showcases import api_suites, machine_of

if __name__ == "__main__":
    sys.exit(run(*api_suites(), machine=machine_of))
