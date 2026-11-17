"""The interfaces into an REE as their committed contracts specify them: the command line and the HTTP API, each on
a page of its own, and the authoring steps both advance.

Everything here is read off the contracts, so a page says what a contract says and nothing a contract does not: the
command line from ``cli-schema``, the API from ``openapi``, each where the contract registry keeps it.
Each model a page names links to its graph on the contracts page.
"""

from __future__ import annotations

from repo2ree_repoview.diagrams.contracts import slug
from repo2ree_repoview.overview.contracts import CliCommand, CliParam, CliSchema, OpenApi, schema_name
from repo2ree_repoview.overview.html import Page, esc, filter_box, link_card, prose, section, table
from repo2ree_repoview.overview.pages.contracts import graph_link

INTERFACES = "interfaces"
CLI_PAGE = "interfaces-cli"
API_PAGE = "interfaces-api"
_PRINTS = {"result": "one result", "bytes": "bytes", "script": "a shell script", "schema": "this contract"}
_NONE = '<span class="muted">&ndash;</span>'


def _part_of() -> str:
    return f'<p class="muted">Part of <a href="{INTERFACES}.html">Interfaces</a>.</p>'


# ================================================
# The hub: both surfaces, and the steps they share
# ================================================


def _steps(cli: CliSchema, api: OpenApi) -> str:
    actions = api.step_actions
    labels = {step.key: step.label for step in cli.steps}
    rows = [
        [
            str(step.order),
            esc(step.label),
            esc(", ".join(labels[key] for key in step.requires)) or _NONE,
            "<br>".join(f"<code>ree {esc(words)}</code>" for words in step.commands),
            "<br>".join(f"<code>{esc(action)}</code>" for action in actions.get(step.key, []))
            or '<span class="no">none in the contract</span>',
        ]
        for step in sorted(cli.steps, key=lambda step: step.order)
    ]
    return (
        "<h3 id='steps'>Authoring steps, on both surfaces</h3>"
        '<p class="lede">The steps of authoring an REE, the steps each needs first, and what advances it: the '
        "<code>ree</code> commands the command line's contract names, and the operations the API's contract names "
        "(<code>listReeSteps</code>). Both read where an REE stands on them from the REE itself.</p>"
        + table(["#", "Step", "Needs", "Command line", "HTTP API"], rows)
    )


def page_interfaces(cli: CliSchema, api: OpenApi) -> Page:
    lede = (
        "How an REE is driven, as the committed contracts specify it. A person or an agent runs <code>ree</code>; "
        "the GUI and HTTP clients call the API, whose workbench runs the same <code>ree</code> commands, spelled "
        "from the same protocol models."
    )
    cards = (
        '<div class="cards">'
        + link_card(CLI_PAGE, "Command line", f"{len(cli.commands)} commands", f"<code>{esc(cli.contract_path)}</code>")
        + link_card(API_PAGE, "HTTP API", f"{api.operations} operations", f"<code>{esc(api.contract_path)}</code>")
        + "</div>"
    )
    teaser = f"{len(cli.commands)} commands and {api.operations} HTTP operations, and the steps both advance"
    return Page(INTERFACES, "Interfaces", teaser, section(INTERFACES, "Interfaces", lede, cards + _steps(cli, api)))


# ================================================
# The command line
# ================================================


def _param(param: CliParam) -> str:
    if param.kind == "argument":
        word = param.name.upper()
    elif param.flag:
        word = f"{param.name}/{param.negation}" if param.negation else param.name
    else:
        listed = bool(param.choices) and len(param.choices) <= 4
        word = f"{param.name} {'|'.join(param.choices) if listed else (param.type or 'VALUE').upper()}"
    word += " …" if param.multiple else ""
    spelled = f"<code>{esc(word)}</code>"
    return spelled if param.required else f'<span class="muted">[</span>{spelled}<span class="muted">]</span>'


def _usage(command: CliCommand) -> str:
    parts = [_param(param) for param in command.params]
    if command.stdin is not None:
        parts.append(f'<span class="muted">&lt; {esc(command.stdin.field)} ({esc(command.stdin.format)})</span>')
    return " ".join(parts)


def _outputs(command: CliCommand) -> str:
    if not command.outputs:
        return esc(_PRINTS[command.stdout])
    return graph_link("cli-schema", slug(" ".join(command.words)), esc(schema_name(command.outputs)))


def _command_rows(commands: tuple[CliCommand, ...]) -> list[list[str]]:
    return [
        [
            f"<code>ree {esc(' '.join(command.words))}</code>",
            prose(command.summary),
            _usage(command),
            _outputs(command),
            "<br>".join(f"<code>{esc(operation)}</code>" for operation in command.operations) or _NONE,
        ]
        for command in commands
    ]


def page_cli(cli: CliSchema) -> Page:
    runs = tuple(command for command in cli.commands if command.runs)
    rest = tuple(command for command in cli.commands if not command.runs)
    headers = ["Command", "Summary", "Arguments", "Outputs", "Protocol operations"]
    exits = table(
        ["Exit", "Meaning"], [[f"<code>{esc(code)}</code>", esc(meaning)] for code, meaning in cli.exit_codes.items()]
    )
    events = table(
        ["Event", "Meaning"], [[f"<code>{esc(name)}</code>", prose(meaning)] for name, meaning in cli.events.items()]
    )
    categories = ", ".join(f"<code>{esc(category)}</code>" for category in cli.failure_categories)
    lede = (
        f"{len(cli.commands)} commands, from <code>{esc(cli.contract_path)}</code>, which "
        "<code>ree schema</code> prints. Each runs against the REE at <code>-C</code>, or the nearest at or above "
        "the current directory, and ends in one result ("
        + graph_link("cli-schema", "result", "<code>ActionResult</code>")
        + "): plain lines for a person, one JSON line on stdout under <code>--json</code>, with the run's events as "
        f"NDJSON on stderr. A failed result carries one of the categories {categories}."
    )
    body = (
        _part_of()
        + "<h3>Exit status</h3>"
        + exits
        + "<h3>Events on stderr under <code>--json</code></h3>"
        + events
        + f"<h3>Commands that run in the REE ({len(runs)})</h3>"
        '<p class="lede">Each runs one or more protocol operations in a session of its own, recorded as an attempt '
        "in the REE's history; one command runs in an REE at a time.</p>"
        + filter_box("cli-runs", "Filter commands…")
        + table(headers, _command_rows(runs), "cli-runs")
        + f"<h3>Reads, and commands that run nothing in the REE ({len(rest)})</h3>"
        + filter_box("cli-reads", "Filter commands…")
        + table(headers, _command_rows(rest), "cli-reads")
    )
    teaser = f"{len(cli.commands)} commands"
    return Page(CLI_PAGE, "Command line", teaser, section(CLI_PAGE, "Command line", lede, body))


# ================================================
# The HTTP API
# ================================================


def page_api(api: OpenApi) -> Page:
    rows = [
        [
            graph_link("openapi", slug(operation.tags[0]), esc(", ".join(operation.tags))) if operation.tags else _NONE,
            f"<code>{esc(method.upper())}</code>",
            f"<code>{esc(path)}</code>",
            f"<code>{esc(operation.operation_id)}</code>",
            esc(operation.summary),
            esc(operation.request) or _NONE,
            esc(operation.response) or _NONE,
        ]
        for path, method, operation in api.each()
    ]
    rows.sort(key=lambda row: (row[0], row[2]))
    lede = (
        f"{api.operations} operations on {len(api.paths)} paths, from <code>{esc(api.contract_path)}</code>. An "
        "operation that runs a command returns a run to follow (<code>observeRun</code>); the API runs it through "
        "the REE's workbench, which runs <code>ree --json</code>. Each tag links to the graph of the models its "
        "operations send and answer with."
    )
    body = (
        _part_of()
        + filter_box("api-table", "Filter operations…")
        + table(["Tag", "Method", "Path", "Operation", "Summary", "Request", "Response"], rows, "api-table")
    )
    teaser = f"{api.operations} operations"
    return Page(API_PAGE, "HTTP API", teaser, section(API_PAGE, "HTTP API", lede, body))
