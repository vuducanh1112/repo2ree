"""The Just recipes, their dependency graph, and how long they took when they ran."""

from __future__ import annotations

from repo2ree_repoview.diagrams.recipes import Recipe
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.figures import DIAGRAMS, diagram
from repo2ree_repoview.overview.html import Page, esc, filter_box, section, table
from repo2ree_repoview.overview.timings import Timing, Timings

# Top-level commands shown, slowest first.
COMMANDS_SHOWN = 30


def seconds(value: float) -> str:
    if value < 10:
        return f"{value:.1f} s"
    if value < 120:
        return f"{value:.0f} s"
    return f"{value / 60:.1f} min"


def took(machines: dict[str, Timing]) -> str:
    """Each machine's median, with how many runs it is of and the last one on hover."""
    cells = []
    for machine, timing in machines.items():
        last = f"last {seconds(timing.last)}"
        if timing.last_revision:
            last += f" at {timing.last_revision[:8]}"
        tip = f"median of {timing.runs} run{'s' if timing.runs != 1 else ''}; {last}"
        if timing.last_exit not in (None, 0):
            tip += f", exit {timing.last_exit}"
        cells.append(f'<span title="{esc(tip)}">{esc(machine)} {esc(seconds(timing.median))}</span>')
    return "<br>".join(cells) or '<span class="muted">not recorded</span>'


def commands_table(timings: Timings) -> str:
    rows = [
        (machine, command, timing)
        for command, machines in timings.commands.items()
        for machine, timing in machines.items()
    ]
    rows.sort(key=lambda row: -row[2].median)
    return table(
        ["Command", "Machine", "Median", "Last", "Runs", "Last exit"],
        [
            [
                f"<code>just {esc(command)}</code>",
                esc(machine),
                esc(seconds(timing.median)),
                esc(seconds(timing.last))
                + (f" <code>{esc(timing.last_revision[:8])}</code>" if timing.last_revision else ""),
                str(timing.runs),
                esc(timing.last_exit if timing.last_exit is not None else ""),
            ]
            for machine, command, timing in rows[:COMMANDS_SHOWN]
        ],
    )


def page_recipes(recipes: dict[str, Recipe], bundle: Bundle, timings: Timings) -> Page:
    listed = sorted(recipes.values(), key=lambda r: (r.group, r.name))
    rows = [
        [
            f"<code>{esc(r.name)}</code>" + (' <span class="badge">private</span>' if r.private else ""),
            esc(r.group),
            esc(r.doc),
            " ".join(f"<code>{esc(p)}</code>" for p in r.parameters),
            " ".join(f"<code>{esc(d.recipe)}</code>" for d in r.dependencies),
            took(timings.recipes.get(r.name, {})),
        ]
        for r in listed
    ]
    public = sum(not r.private for r in listed)
    body = filter_box("recipe-table", "Filter recipes…") + table(
        ["Recipe", "Group", "What it does", "Parameters", "Runs first", "Took"], rows, "recipe-table"
    )
    body += diagram(
        bundle,
        DIAGRAMS / "just-recipes.svg",
        "Recipe dependency graph",
        "Prerequisites point to the recipe that consumes them.",
    )
    if timings.commands:
        body += (
            "<h3>Recorded commands</h3>"
            '<p class="lede">Each command as it was typed, from start to end, slowest first. A recipe\'s own time '
            "above leaves out what ran before it, and recipes that run side by side overlap.</p>"
            + commands_table(timings)
        )
    recorded = (
        f" Times are medians per machine of {timings.invocations} recorded invocations (<code>logs/just/</code>)."
        if timings.invocations
        else " No invocation is recorded yet: the dev shell's <code>just</code> records into <code>logs/just/</code>."
    )
    lede = f"{public} public recipes and {len(listed) - public} private ones, from <code>just --dump</code>.{recorded}"
    body = section("just-recipes", "Just recipes", lede, body)
    return Page("just-recipes", "Just recipes", f"{public} public recipes", body)
