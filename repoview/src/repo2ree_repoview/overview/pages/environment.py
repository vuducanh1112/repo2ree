"""The environment-variable contract, a subpage of the contracts page."""

from __future__ import annotations

from collections import Counter

from repo2ree_repoview.overview.contracts import Environment
from repo2ree_repoview.overview.html import Page, esc, filter_box, section, table

ENVIRONMENT_PAGE = "contracts-environment"


def page_environment(environment: Environment) -> Page:
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
        f"The environment-variable contract (<code>{esc(environment.contract_path)}</code>), rendered by "
        f"<code>{esc(environment.rendered_by)}</code>: " + ", ".join(f"{n} {k}" for k, n in kinds.most_common()) + "."
    )
    body = section(
        ENVIRONMENT_PAGE,
        "Environment variables",
        lede,
        filter_box("env-table", "Filter variables…")
        + table(["Variable", "Owner", "Kind", "Default"], rows, "env-table"),
    )
    return Page(ENVIRONMENT_PAGE, "Environment variables", f"{len(environment.variables)} environment variables", body)
