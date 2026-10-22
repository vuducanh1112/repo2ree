"""The small HTML vocabulary every page is written in."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def prose(value: object) -> str:
    """Escaped text with `backticked` spans as code."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(value))


def section(anchor: str, title: str, lede: str, body: str) -> str:
    return f'<section id="{anchor}"><h2>{esc(title)}</h2><p class="lede">{lede}</p>{body}</section>'


def table(headers: list[str], rows: list[list[str]], ident: str = "") -> str:
    head_row = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr data-row>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    opening = f'<table id="{ident}">' if ident else "<table>"
    return f"{opening}<thead><tr>{head_row}</tr></thead><tbody>{body}</tbody></table>"


def filter_box(target: str, placeholder: str) -> str:
    return f'<input class="filter" data-target="{target}" placeholder="{esc(placeholder)}">'


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    teaser: str
    body: str
