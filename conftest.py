from __future__ import annotations

import os
from pathlib import Path

from repo2ree_testbed.artifacts import run_dir

pytest_plugins = ["repo2ree_testbed.pytest_plugin"]

run_dir()

HYPOTHESIS_HOME = Path(__file__).parent / "test-artifacts" / "cache" / "hypothesis"

os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(HYPOTHESIS_HOME))
