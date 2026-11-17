"""The API's OpenAPI document, as ``contracts/openapi.json`` publishes it (``scripts/contracts.py``).

The committed document is the automation-client contract; the FastAPI app is one implementation of it.
"""

from __future__ import annotations

import json

from repo2ree_api.main import app


def openapi_document() -> str:
    """The generated document in its canonical committed serialization."""
    return json.dumps(app.openapi(), indent=2) + "\n"
