from __future__ import annotations

import json

from repo2ree_ree.model import CURRENT_SCHEMA_VERSION, Ree


def schema_document() -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:repo2ree:ree:{CURRENT_SCHEMA_VERSION}",
        **Ree.model_json_schema(mode="validation"),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
