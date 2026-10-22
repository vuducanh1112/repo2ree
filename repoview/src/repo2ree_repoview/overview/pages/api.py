"""The OpenAPI contract's operations."""

from __future__ import annotations

from repo2ree_repoview.overview.contracts import OpenApi
from repo2ree_repoview.overview.html import Page, esc, filter_box, section, table


def page_api(api: OpenApi) -> Page:
    rows = [
        [
            esc(", ".join(operation.tags)),
            f"<code>{esc(method.upper())}</code>",
            f"<code>{esc(path)}</code>",
            esc(operation.summary),
        ]
        for path, methods in api.paths.items()
        for method, operation in methods.items()
    ]
    rows.sort(key=lambda r: (r[0], r[2]))
    lede = f"{api.operations} operations on {len(api.paths)} paths, from <code>contracts/openapi.json</code>."
    body = section(
        "api",
        "API",
        lede,
        filter_box("api-table", "Filter operations…") + table(["Tag", "Method", "Path", "Summary"], rows, "api-table"),
    )
    return Page("api", "API", f"{api.operations} operations", body)
