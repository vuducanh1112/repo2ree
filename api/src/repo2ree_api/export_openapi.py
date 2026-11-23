from __future__ import annotations

import json

from repo2ree_api.main import app


def openapi_document() -> str:
    return json.dumps(app.openapi(), indent=2) + "\n"
