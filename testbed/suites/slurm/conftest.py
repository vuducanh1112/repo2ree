"""The system suite's fixtures and its typed client, on a stack whose workbench is installed on a Slurm node."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))

from system_client import api, new_ree, pytest_collection_modifyitems
from typed_client import client

__all__ = ["api", "client", "new_ree", "pytest_collection_modifyitems"]
