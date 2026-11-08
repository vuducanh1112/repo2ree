"""The system suite's fixtures, on a stack whose workbench is installed on a machine of its own."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))

from system_client import api, new_ree, pytest_collection_modifyitems

__all__ = ["api", "new_ree", "pytest_collection_modifyitems"]
