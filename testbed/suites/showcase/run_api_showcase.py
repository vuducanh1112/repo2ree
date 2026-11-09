#!/usr/bin/env python3
"""The API showcases of one machine, as a stack's client (``python -m repo2ree_testbed e2e --script``)."""

import sys

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.showcases import api_suites, requested_environment

if __name__ == "__main__":
    environment = requested_environment()
    suites = api_suites(environment)
    if not suites:
        sys.exit(f"no showcase runs on {environment}")
    sys.exit(run(*suites))
