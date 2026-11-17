"""The showcases' fixtures: the same tests on two surfaces, the API (the default) and the ``ree`` command line.

``E2E_SHOWCASE_SURFACE=cli`` (``run_cli_showcase.py``) gives the tests a client that runs ``ree`` on the test's
machine; otherwise the system suite's typed client drives the stack's API.
"""

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
