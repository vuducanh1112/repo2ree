#!/usr/bin/env python3
import sys
from pathlib import Path

from repo2ree_testbed.pytest_suite import run

if __name__ == "__main__":
    sys.exit(run(Path(__file__).resolve().parent))
