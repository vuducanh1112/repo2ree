#!/usr/bin/env python3
import sys

from repo2ree_testbed.pytest_suite import run
from repo2ree_testbed.showcases import REAL_WORLD, real_world_machine_of, real_world_suite

if __name__ == "__main__":
    sys.exit(run(*(real_world_suite(name) for name in REAL_WORLD), machine=real_world_machine_of))
