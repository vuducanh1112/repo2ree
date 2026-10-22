"""The OpenAPI contract's operations."""

from __future__ import annotations

import json

from repo2ree_repoview.overview.html import esc, filter_box, section, table
from repo2ree_repoview.overview.inputs import (
    OPENAPI,
)


def page_api() -> str:
    spec = json.loads(OPENAPI.read_text())
    rows = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            rows.append(
                [
                    esc(", ".join(operation.get("tags", []))),
                    f"<code>{esc(method.upper())}</code>",
                    f"<code>{esc(path)}</code>",
                    esc(operation.get("summary", "")),
                ]
            )
    rows.sort(key=lambda r: (r[0], r[2]))
    lede = f"{len(rows)} operations on {len(spec['paths'])} paths, from <code>contracts/openapi.json</code>."
    return section(
        "api",
        "API",
        lede,
        filter_box("api-table", "Filter operations…") + table(["Tag", "Method", "Path", "Summary"], rows, "api-table"),
    )
