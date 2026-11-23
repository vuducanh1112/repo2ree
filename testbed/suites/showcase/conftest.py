import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "system"))

from system_client import api

SURFACE_VARIABLE = "E2E_SHOWCASE_SURFACE"

if os.environ.get(SURFACE_VARIABLE) == "cli":
    from cli_client import client, new_ree, pytest_collection_modifyitems
else:
    from system_client import new_ree, pytest_collection_modifyitems
    from typed_client import client

__all__ = ["api", "client", "new_ree", "pytest_collection_modifyitems"]
