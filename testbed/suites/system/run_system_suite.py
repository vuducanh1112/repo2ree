#!/usr/bin/env python3
"""The system suite as a stack's client (``python -m repo2ree_testbed e2e --script``)."""

import sys
from pathlib import Path

from repo2ree_testbed.pytest_suite import run

if __name__ == "__main__":
    sys.exit(run(Path(__file__).resolve().parent))
