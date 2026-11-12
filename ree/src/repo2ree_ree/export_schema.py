from __future__ import annotations

import json
from pathlib import Path

from repo2ree_ree.layout import layout_document
from repo2ree_ree.model import CURRENT_SCHEMA_VERSION, Ree

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "ree"
SCHEMA_PATH = CONTRACT / "ree.schema.json"
LAYOUT_PATH = CONTRACT / "layout.json"


def schema_document() -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:repo2ree:ree:{CURRENT_SCHEMA_VERSION}",
        **Ree.model_json_schema(mode="validation"),
    }
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA_PATH.write_text(schema_document(), encoding="utf-8")
    LAYOUT_PATH.write_text(layout_document(), encoding="utf-8")


if __name__ == "__main__":
    main()
