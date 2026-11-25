import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "showcase"))

from cli_client import client, new_ree, pytest_collection_modifyitems

__all__ = ["client", "new_ree", "pytest_collection_modifyitems"]
