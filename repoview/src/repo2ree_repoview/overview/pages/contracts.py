"""The committed contracts: what each binds and between whom, and each drawn as graphs of its models.

The drawings are those ``just generate-contract-graphs`` made of each contract, one per entry point it names.
"""

from __future__ import annotations

from repo2ree_repoview.diagrams.contracts import Contract, contracts, drawing_path
from repo2ree_repoview.overview.bundle import Bundle, Origin
from repo2ree_repoview.overview.contracts import CONTRACT_FILES
from repo2ree_repoview.overview.figures import DIAGRAMS, diagram_origin
from repo2ree_repoview.overview.html import Page, esc, prose, section, table
from repo2ree_repoview.stamp import read_svg_stamp

CONTRACTS = "contracts"
GRAPHS = DIAGRAMS / "contracts"


def graph_anchor(contract: str, entry: str) -> str:
    """Where the drawing of ``entry``, an entry point of ``contract``, sits on the contracts page."""
    return f"graph-{contract}-{entry}"


def graph_link(contract: str, entry: str, text: str) -> str:
    return f'<a href="{CONTRACTS}.html#{esc(graph_anchor(contract, entry))}">{text}</a>'


def _files() -> str:
    rows = [
        [
            f"<code>{esc(contract.path)}</code>",
            prose(contract.binds),
            prose(contract.between),
            f"<code>just {esc(contract.written_by)}</code>",
            f'<code title="sha256 {contract.digest}">{contract.digest[:12]}</code>',
        ]
        for contract in CONTRACT_FILES
        if contract.file.is_file()
    ]
    return (
        "<h3 id='files'>Contract files</h3>"
        '<p class="lede">Each is generated from the code that implements it and committed; a test fails when the '
        "code and the committed contract differ, so a change to an interface is a change to its contract.</p>"
        + table(["Contract", "Binds", "Between", "Written by", "sha256"], rows)
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


def page_contracts(bundle: Bundle) -> Page:
    drawn = contracts()
    index = " · ".join(f'<a href="#graphs-{esc(contract.key)}">{esc(contract.title)}</a>' for contract in drawn)
    lede = (
        "The contracts the repository commits, and each drawn from the entry points it names: a box for each "
        "model, its fields (<code>?</code> where one may be left out), and an edge to each model a field holds "
        "(<code>[*]</code> a list of it, <code>{*}</code> a map of it, <code>|</code> one of a union). The REE "
        'document\'s own anatomy is on the <a href="ree.html">REE</a> page; the interfaces these contracts specify '
        f'are on the <a href="interfaces.html">Interfaces</a> page.</p><p class="lede">Graphs: {index}'
    )
    body = _files() + "".join(_graphs(bundle, contract) for contract in drawn)
    graphs = sum(len(contract.entries) for contract in drawn)
    teaser = f"{len(CONTRACT_FILES)} committed contracts, drawn as {graphs} graphs of their models"
    return Page(CONTRACTS, "Contracts", teaser, section(CONTRACTS, "Contracts", lede, body))
