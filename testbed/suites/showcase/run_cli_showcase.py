#!/usr/bin/env python3
"""The showcases through the command line, as a stack's client (``python -m repo2ree_testbed cli-showcase run``):
each test runs ``ree`` on the machine its showcase names."""

import os
import sys

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.showcases import api_suites, machine_of

if __name__ == "__main__":
    os.environ["E2E_SHOWCASE_SURFACE"] = "cli"
    sys.exit(run(*api_suites(), machine=machine_of))
