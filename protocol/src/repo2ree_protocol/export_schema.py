"""The protocol as JSON Schema, as ``contracts/protocol/protocol.schema.json`` publishes it
(``scripts/contracts.py``)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import create_model

from repo2ree_protocol.command import Command
from repo2ree_protocol.frames import Frame
from repo2ree_protocol.outputs import OUTPUTS
from repo2ree_protocol.queries import REPLIES, verb_of
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.workbench import WorkbenchHello, WorkbenchWsMessage, WorkbenchWsRequest

MESSAGES: dict[str, Any] = {
    "Command": Command,
    "ActionResult": ActionResult,
    "Frame": Frame,
    "WorkbenchHello": WorkbenchHello,
    "WorkbenchWsRequest": WorkbenchWsRequest,
    "WorkbenchWsMessage": WorkbenchWsMessage,
}


def schema_document() -> str:
    fields: dict[str, Any] = {f"message:{name}": (shape, ...) for name, shape in MESSAGES.items()}
    fields |= {f"outputs:{operation}": (shape, ...) for operation, shape in OUTPUTS.items()}
    fields |= {f"query:{verb_of(query)}": (query, ...) for query in REPLIES}
    fields |= {f"reply:{verb_of(query)}": (reply, ...) for query, reply in REPLIES.items() if reply is not None}
    root = create_model("ProtocolDocument", **fields).model_json_schema(mode="validation")
    properties = {
        name: {key: value for key, value in entry.items() if key != "title"}
        for name, entry in root["properties"].items()
    }
    queries = {
        verb_of(query): {
            "query": properties[f"query:{verb_of(query)}"],
            "reply": properties[f"reply:{verb_of(query)}"]
            if reply is not None
            else {"contentMediaType": "application/octet-stream"},
        }
        for query, reply in REPLIES.items()
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
