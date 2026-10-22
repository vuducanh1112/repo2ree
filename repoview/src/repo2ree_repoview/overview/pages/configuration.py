"""The environment-variable contract."""

from __future__ import annotations

from collections import Counter

from repo2ree_repoview.overview.contracts import Environment
from repo2ree_repoview.overview.html import Page, esc, filter_box, section, table


def page_configuration(environment: Environment) -> Page:
    rows = []
    for name, variable in sorted(environment.variables.items()):
        default = variable.value_schema.default
        rows.append(
            [
                f"<code>{esc(name)}</code>",
                esc(variable.owner),
                esc(variable.kind),
                f"<code>{esc(default)}</code>" if default not in ("", None) else '<span class="muted">—</span>',
            ]
        )
    for pattern, variable in environment.patterns.items():
        rows.append(
            [
                f"<code>{esc(pattern)}</code>",
                esc(variable.owner),
                esc(variable.kind),
                '<span class="muted">pattern</span>',
            ]
        )
    kinds = Counter(variable.kind for variable in environment.variables.values())
    lede = (
        "The environment-variable contract (<code>contracts/config/environment.json</code>): "
        + ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        + "."
    )
    body = section(
        "configuration",
        "Configuration",
        lede,
        filter_box("env-table", "Filter variables…")
        + table(["Variable", "Owner", "Kind", "Default"], rows, "env-table"),
    )
    return Page("configuration", "Configuration", f"{len(environment.variables)} environment variables", body)
