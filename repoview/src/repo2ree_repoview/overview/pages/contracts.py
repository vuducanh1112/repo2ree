from __future__ import annotations

from repo2ree_repoview.diagrams.contracts import Contract, contracts, drawing_path
from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.overview.contracts import Environment
from repo2ree_repoview.overview.exports import ContractName, Contracts, GeneratedContract
from repo2ree_repoview.overview.figures import DIAGRAMS, diagram_origin
from repo2ree_repoview.overview.html import Page, esc, link_card, prose, section, table
from repo2ree_repoview.overview.pages.environment import ENVIRONMENT_PAGE
from repo2ree_repoview.stamp import read_svg_stamp

CONTRACTS = "contracts"
GRAPHS = DIAGRAMS / "contracts"
SUBPAGES: dict[str, str] = {"environment": ENVIRONMENT_PAGE}


def graph_anchor(contract: ContractName, entry: str) -> str:
    return f"graph-{contract}-{entry}"


def graph_link(contract: ContractName, entry: str, text: str) -> str:
    return f'<a href="{CONTRACTS}.html#{esc(graph_anchor(contract, entry))}">{text}</a>'


def _path(contract: GeneratedContract) -> str:
    code = f"<code>{esc(contract.path)}</code>"
    page = SUBPAGES.get(contract.name)
    return f'<a href="{page}.html">{code}</a>' if page else code


def _files(registry: Contracts) -> str:
    rows = [
        [
            _path(contract),
            prose(contract.summary),
            prose(contract.between),
            f"<code>{esc(contract.rendered_by)}</code>",
            f'<code title="sha256 {contract.digest}">{contract.digest[:12]}</code>',
        ]
        for contract in registry.contracts
        if contract.file.is_file()
    ]
    fixtures = [[f"<code>{esc(path)}</code>"] for path in registry.fixtures]
    return (
        "<h3 id='files'>Contract files</h3>"
        '<p class="lede">Each is rendered from the code that implements it and committed '
        "(<code>scripts/contracts.py</code>); <code>just check-contracts</code> fails when the code and a committed "
        "contract differ, so a change to an interface is a change to its contract.</p>"
        + table(["Contract", "Binds", "Between", "Rendered by", "sha256"], rows)
        + "<h3 id='fixtures'>Fixtures</h3>"
        '<p class="lede">Written by hand, and read by the tests that hold implementations to them.</p>'
        + table(["Fixture"], fixtures)
    )


def _graphs(bundle: Bundle, contract: Contract) -> str:
    drawn = []
    origin = ""
    for entry in contract.entries:
        path = drawing_path(GRAPHS, contract, entry)
        stamp = read_svg_stamp(path) if path.is_file() else None
        origin = origin or diagram_origin(bundle, stamp)
        relative = bundle.copy(
            path,
            f"diagrams/{path.relative_to(DIAGRAMS)}",
            Origin(kind="diagram", revision=stamp.revision if stamp else ""),
        )
        models = len(contract.reached(entry))
        title = f'{esc(entry.title)} <span class="muted">{models} model{"s" if models != 1 else ""}</span>'
        shown = (
            f'<div class="diagram"><a href="{esc(relative)}"><img src="{esc(relative)}" alt="{esc(entry.title)}" '
            'loading="lazy"></a></div>'
            if relative
            else '<p class="state-missing">Missing: run <code>just generate-contract-graphs</code>.</p>'
        )
        anchor = graph_anchor(contract.key, entry.slug)
        drawn.append(f'<details id="{esc(anchor)}"><summary>{title}</summary>{shown}</details>')
    return (
        f"<h3 id='graphs-{esc(contract.key)}'>{esc(contract.title)} <code>{esc(contract.path)}</code></h3>"
        f'<p class="muted">{len(contract.entries)} entry points. {origin}</p>' + "".join(drawn)
    )


def page_contracts(bundle: Bundle, registry: Contracts, environment: Environment) -> Page:
    drawn = contracts(registry)
    index = " · ".join(f'<a href="#graphs-{esc(contract.key)}">{esc(contract.title)}</a>' for contract in drawn)
    lede = (
        "The contracts the repository commits, and each drawn from the entry points it names: a box for each "
        "model, its fields (<code>?</code> where one may be left out), and an edge to each model a field holds "
        "(<code>[*]</code> a list of it, <code>{*}</code> a map of it, <code>|</code> one of a union). The REE "
        'document\'s own anatomy is on the <a href="ree.html">REE</a> page; the interfaces these contracts specify '
        f'are on the <a href="interfaces.html">Interfaces</a> page.</p><p class="lede">Graphs: {index}'
    )
    cards = (
        '<div class="cards">'
        + link_card(
            ENVIRONMENT_PAGE,
            "Environment variables",
            f"{len(environment.variables)} variables",
            f"<code>{esc(environment.contract_path)}</code>",
        )
        + "</div>"
    )
    body = cards + _files(registry) + "".join(_graphs(bundle, contract) for contract in drawn)
    graphs = sum(len(contract.entries) for contract in drawn)
    teaser = f"{len(registry.contracts)} committed contracts, drawn as {graphs} graphs of their models"
    return Page(CONTRACTS, "Contracts", teaser, section(CONTRACTS, "Contracts", lede, body))
