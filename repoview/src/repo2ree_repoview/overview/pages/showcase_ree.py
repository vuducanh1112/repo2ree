"""One showcase's final REE: what its authoring test sealed, and how inference stands in it."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from repo2ree_repoview.overview.bundle import source_name
from repo2ree_repoview.overview.exports import Showcase, ShowcaseTest
from repo2ree_repoview.overview.html import Page, esc, section, table
from repo2ree_repoview.overview.showcase_ree import OVERLAY, Entry, Script, SealedRee, TargetResult, Written

WRITTEN: dict[Written, tuple[str, str]] = {
    "inferred": ("ok", "as inferred"),
    "chosen_over": ("ex", "chosen over inference"),
    "no_candidate": ("no", "inference proposed nothing"),
    "not_asked": ("no", "inference not asked"),
}
STATUS_TONE = {"complete": "ok", "needs_input": "ex", "not_inferred": "no"}


def slug(name: str) -> str:
    return f"showcase-ree-{name}"


def authoring_test(showcase: Showcase) -> ShowcaseTest | None:
    """The API authoring test whose REE the page shows."""
    return next(
        (t for t in showcase.tests if t.surface == "api" and t.workflow == "authoring" and t.test is not None), None
    )


def badge(written: Written) -> str:
    tone, label = WRITTEN[written]
    return f'<span class="{tone}">{esc(label)}</span>'


def size(count: int) -> str:
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if count >= scale:
            return f"{count / scale:.1f} {unit}"
    return f"{count} B"


def code_block(text: str) -> str:
    return f'<pre class="code">{esc(text)}</pre>'


def answered(result: TargetResult | None) -> str:
    if result is None:
        return ""
    return (
        f'<span class="{STATUS_TONE[result.status]}">{esc(result.status)}</span>'
        f' <span class="muted">{esc(result.application)}</span>'
    )


def script_rows(ree: SealedRee) -> list[list[str]]:
    rows = []
    for script in ree.scripts:
        name = script.path.removeprefix(OVERLAY)
        rules = "<br>".join(dict.fromkeys(f"<code>{esc(p.candidate.inference_rule)}</code>" for p in script.proposals))
        rows.append(
            [
                f'<a href="#script-{esc(name)}"><code>{esc(name)}</code></a>',
                badge(script.written),
                answered(script.answer),
                rules,
            ]
        )
    return rows


def labelled(label: str, body: str) -> str:
    return f'<div><div class="muted">{label}</div>{code_block(body)}</div>'


def script_section(script: Script) -> str:
    name = script.path.removeprefix(OVERLAY)
    parts = [f'<h4 id="script-{esc(name)}"><code>{esc(name)}</code> · {badge(script.written)}</h4>']
    proposal = script.proposal
    if proposal and script.written == "inferred":
        warnings = ", ".join(f"<code>{esc(w.code)}</code>" for w in proposal.candidate.warnings)
        parts.append(
            f'<p class="muted">The candidate of <code>{esc(proposal.candidate.inference_rule)}</code> '
            f"({esc(proposal.candidate.decision_leaf)}), written as proposed"
            + (f"; its warnings: {warnings}" if warnings else "")
            + ".</p>"
            + code_block(script.body)
        )
    elif proposal and script.written == "chosen_over":
        rule = f"<code>{esc(proposal.candidate.inference_rule)}</code> ({esc(proposal.candidate.decision_leaf)})"
        warnings = ", ".join(f"<code>{esc(w.code)}</code>" for w in proposal.candidate.warnings)
        others = [p for p in script.proposals if p.candidate.body != proposal.candidate.body]
        parts.append(
            '<div class="compare">'
            + labelled(f"What inference proposed: {rule}", proposal.candidate.body)
            + labelled("What was chosen", script.body)
            + "</div>"
            + (f'<p class="muted">Its warnings: {warnings}.</p>' if warnings else "")
            + f"<details><summary>the difference</summary>{code_block(script.diff())}</details>"
            + "".join(
                f"<details><summary>also proposed: <code>{esc(p.candidate.inference_rule)}</code></summary>"
                f"{code_block(p.candidate.body)}</details>"
                for p in {p.candidate.body: p for p in others}.values()
            )
        )
    elif script.written == "no_candidate":
        parts.append(
            f'<p class="muted">Inference was asked and answered {answered(script.answer)} with no candidate.</p>'
            + code_block(script.body)
        )
    else:
        parts.append('<p class="muted">No inference request named this script before the seal.</p>')
        parts.append(code_block(script.body))
    return "".join(parts)


def request_rows(ree: SealedRee) -> list[list[str]]:
    rows = []
    for index, request in enumerate(ree.requests, 1):
        for result in request.results:
            candidates = "<br>".join(
                f'<code>{esc(c.inference_rule)}</code> <span class="muted">{esc(c.decision_leaf)}'
                + (f" · {esc(', '.join(w.code for w in c.warnings))}" if c.warnings else "")
                + "</span>"
                for c in result.candidates
            )
            rows.append(
                [
                    f'{index} <span class="muted"><code>{esc(request.commit[:10])}</code></span>',
                    f"<code>{esc(result.target.path)}</code>",
                    f'<span class="{STATUS_TONE[result.status]}">{esc(result.status)}</span>',
                    esc(result.application),
                    candidates or '<span class="muted">none</span>',
                ]
            )
    return rows


@dataclass
class _Folder:
    folders: dict[str, _Folder] = field(default_factory=dict)
    files: list[tuple[str, Entry]] = field(default_factory=list)

    def count(self) -> int:
        return len(self.files) + sum(folder.count() for folder in self.folders.values())


def _folder(entries: tuple[Entry, ...]) -> _Folder:
    root = _Folder()
    for entry in entries:
        *parents, name = entry.path.split("/")
        folder = root
        for parent in parents:
            folder = folder.folders.setdefault(parent, _Folder())
        folder.files.append((name, entry))
    return root


def file_leaf(name: str, entry: Entry) -> str:
    stored = '<span class="lfs">LFS</span>' if entry.lfs else "Git"
    meta = f'<span class="meta">{size(entry.lfs.size if entry.lfs else entry.size)} · {stored}</span>'
    if entry.text is None:
        return f"<li>{esc(name)}{meta}</li>"
    return f"<li><details><summary>{esc(name)}{meta}</summary>{code_block(entry.text)}</details></li>"


def folder_items(folder: _Folder) -> str:
    folders = "".join(
        f'<li><details open><summary><b>{esc(name)}/</b><span class="meta">{sub.count()} files</span></summary>'
        f"<ul>{folder_items(sub)}</ul></details></li>"
        for name, sub in sorted(folder.folders.items())
    )
    return folders + "".join(file_leaf(name, entry) for name, entry in sorted(folder.files, key=lambda f: f[0]))


def file_tree(entries: tuple[Entry, ...]) -> str:
    """The REE's files as a tree, folders open, each text file opening to its contents."""
    return f'<div class="filetree"><ul>{folder_items(_folder(entries))}</ul></div>'


def ree_body(ree: SealedRee, test: ShowcaseTest) -> str:
    written = Counter(script.written for script in ree.scripts)
    tally = " · ".join(f"{written[kind]} {badge(kind)}" for kind in WRITTEN if written[kind])
    sealed = ree.sealed
    cards = [
        ("Test", f"<code>{esc(test.test or '')}</code>"),
        ("Run", f"<code>{esc(test.run or '')}</code>"),
        ("REE", f"<code>{esc(ree.ree_id)}</code>"),
        ("Sealed", f"{esc(sealed.sealed_at)}<br><code>{esc(sealed.ree_digest)}</code>" if sealed else "—"),
        ("Scripts", tally or '<span class="muted">none</span>'),
    ]
    after = (
        f'<p class="muted">{ree.after_seal} operation(s) followed the seal; they are not shown.</p>'
        if ree.after_seal
        else ""
    )
    history = "".join(
        f"<li><code>{esc(op.operation)}</code> "
        f'<span class="{"ok" if op.outcome == "succeeded" else "no"}">{esc(op.outcome or "unrecorded")}</span> '
        f'<span class="muted"><code>{esc(op.commit[:10])}</code></span></li>'
        for op in ree.operations
    )
    return (
        '<div class="cards">'
        + "".join(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in cards)
        + "</div>"
        + "<h3>Scripts</h3>"
        + table(["Script", "Written", "Inference answered", "Inference proposed"], script_rows(ree))
        + "".join(script_section(script) for script in ree.scripts)
        + "<h3>What inference was asked</h3>"
        + (
            table(["Request", "Target", "Status", "Application", "Candidates"], request_rows(ree))
            if ree.requests
            else '<p class="muted">Inference was not asked before the seal.</p>'
        )
        + "<h3>Files at the seal</h3>"
        + file_tree(ree.files)
        + "<h3>Operations to the seal</h3>"
        + f"<ol>{history}</ol>{after}"
        + f'<p class="muted">Read from <code>{esc(source_name(ree.source))}</code> at <code>{esc(ree.seal)}</code>.</p>'
    )


def page_showcase_ree(showcase: Showcase, test: ShowcaseTest | None, ree: SealedRee | None) -> Page:
    title = f"{showcase.name} REE"
    lede = (
        f'The REE the <a href="showcase-gate.html#showcase-{esc(showcase.name)}">{esc(showcase.name)}</a> showcase\'s '
        "authoring test sealed, as the test preserved it. Each script is matched against what inference proposed "
        "in the REE's own history: written as inferred, chosen over what inference proposed, written where inference "
        "proposed nothing, or written without inference being asked."
    )
    if test is None:
        body = '<p class="muted">This clone has no run of its API authoring test.</p>'
    elif ree is None:
        body = '<p class="no">Its authoring test preserved no sealed REE.</p>'
    else:
        body = ree_body(ree, test)
    teaser = f"What {showcase.name}'s authoring test sealed"
    return Page(slug(showcase.name), title, teaser, section(slug(showcase.name), title, lede, body))
