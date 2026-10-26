"""Running Graphviz on the DOT the views write."""

from __future__ import annotations

import json
import re
import subprocess


def quote(name: str) -> str:
    """A DOT identifier or label, quoted and escaped; DOT reads UTF-8, so other characters stay as they are."""
    return json.dumps(name, ensure_ascii=False)


def render(source: str, format: str) -> bytes:  # noqa: A002 - dot's own name for it
    return subprocess.run(["dot", f"-T{format}"], input=source.encode(), capture_output=True, check=True).stdout


def inline_svg(source: str, *, css_class: str = "") -> str:
    """An SVG to embed in a page: no XML prolog, and with ``css_class``, sized by the page rather than in points."""
    svg = render(source, "svg").decode()
    svg = svg[svg.index("<svg") :]
    if css_class:
        svg = re.sub(r'width="[\d.]+pt" height="[\d.]+pt"', f'class="{css_class}"', svg, count=1)
    return svg
