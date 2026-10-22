"""The environment-variable contract."""

from __future__ import annotations

import json
from collections import Counter

from repo2ree_repoview.overview.html import esc, filter_box, section, table
from repo2ree_repoview.overview.inputs import (
    ENVIRONMENT,
)


def page_configuration() -> str:
    contract = json.loads(ENVIRONMENT.read_text())
    rows = []
    for name, variable in sorted(contract["variables"].items()):
        default = variable.get("schema", {}).get("default", "")
        rows.append(
            [
                f"<code>{esc(name)}</code>",
                esc(variable.get("owner", "")),
                esc(variable.get("kind", "")),
                f"<code>{esc(default)}</code>" if default not in ("", None) else '<span class="muted">—</span>',
            ]
        )
    for pattern, variable in contract.get("patterns", {}).items():
        rows.append(
            [
                f"<code>{esc(pattern)}</code>",
                esc(variable.get("owner", "")),
                esc(variable.get("kind", "")),
                '<span class="muted">pattern</span>',
            ]
        )
    kinds = Counter(v.get("kind", "") for v in contract["variables"].values())
    lede = (
        "The environment-variable contract (<code>contracts/config/environment.json</code>): "
        + ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        + "."
    )
    return section(
        "configuration",
        "Configuration",
        lede,
        filter_box("env-table", "Filter variables…")
        + table(["Variable", "Owner", "Kind", "Default"], rows, "env-table"),
    )
