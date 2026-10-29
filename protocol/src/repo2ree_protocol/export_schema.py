from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import create_model

from repo2ree_protocol.command import Command
from repo2ree_protocol.frames import Frame
from repo2ree_protocol.outputs import OUTPUTS
from repo2ree_protocol.provider import ProviderHello, ProviderWsMessage, ProviderWsRequest
from repo2ree_protocol.queries import QUERIES
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import WorkbenchHello, WorkbenchWsMessage, WorkbenchWsRequest

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "contracts" / "protocol" / "protocol.schema.json"

MESSAGES: dict[str, Any] = {
    "Command": Command,
    "ActionResult": ActionResult,
    "Frame": Frame,
    "WorkbenchHello": WorkbenchHello,
    "WorkbenchWsRequest": WorkbenchWsRequest,
    "WorkbenchWsMessage": WorkbenchWsMessage,
    "ProviderHello": ProviderHello,
    "ProviderWsRequest": ProviderWsRequest,
    "ProviderWsMessage": ProviderWsMessage,
}


def schema_document() -> str:
    fields: dict[str, Any] = {f"message:{name}": (shape, ...) for name, shape in MESSAGES.items()}
    fields |= {f"outputs:{operation}": (shape, ...) for operation, shape in OUTPUTS.items()}
    fields |= {f"query:{name}": (reply, ...) for name, (reply, _flags) in QUERIES.items() if reply is not None}
    root = create_model("ProtocolDocument", **fields).model_json_schema(mode="validation")
    properties = {
        name: {key: value for key, value in entry.items() if key != "title"}
        for name, entry in root["properties"].items()
    }
    queries = {
        name: {
            "flags": list(flags),
            "reply": properties[f"query:{name}"]
            if reply is not None
            else {"contentMediaType": "application/octet-stream"},
        }
        for name, (reply, flags) in QUERIES.items()
    }
    document = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:repo2ree:protocol",
        "x-messages": {name: properties[f"message:{name}"] for name in MESSAGES},
        "x-outputs": {operation: properties[f"outputs:{operation}"] for operation in OUTPUTS},
        "x-queries": queries,
        "$defs": root["$defs"],
    }
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(schema_document(), encoding="utf-8")


if __name__ == "__main__":
    main()
