from __future__ import annotations

import html
import re
from dataclasses import dataclass


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def prose(value: object) -> str:
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(value))


def section(anchor: str, title: str, lede: str, body: str) -> str:
    intro = f'<p class="lede">{lede}</p>' if lede else ""
    return f'<section id="{anchor}"><h2>{esc(title)}</h2>{intro}{body}</section>'


def table(headers: list[str], rows: list[list[str]], ident: str = "") -> str:
    head_row = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr data-row>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    opening = f'<table id="{ident}">' if ident else "<table>"
    return f"{opening}<thead><tr>{head_row}</tr></thead><tbody>{body}</tbody></table>"


def rule_anchor(rule: str) -> str:
    return f"rule-{rule}"


def rule_link(rule: str) -> str:
    return f'<a href="coverage.html#{esc(rule_anchor(rule))}"><code>{esc(rule)}</code></a>'


FRAME = "evidence"


def in_frame(target: str, origin: str, anchor: str = "") -> str:
    return f"{FRAME}.html?from={origin}#{target}" + (f"#{anchor}" if anchor else "")


def filter_box(target: str, placeholder: str) -> str:
    return f'<input class="filter" data-target="{target}" placeholder="{esc(placeholder)}">'


def link_card(slug: str, title: str, value: str, note: str) -> str:
    return (
        f'<a class="card link" href="{slug}.html"><div class="k">{esc(title)}</div><div class="v">{esc(value)}</div>'
        f'<div class="muted">{note}</div></a>'
    )


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    teaser: str
    body: str
