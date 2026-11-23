from __future__ import annotations

import json
import re
import subprocess


def quote(name: str) -> str:
    return json.dumps(name, ensure_ascii=False)


def render(source: str, format: str) -> bytes:  # noqa: A002
    result = subprocess.run(["dot", f"-T{format}"], input=source.encode(), capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"dot -T{format} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def inline_svg(source: str, *, css_class: str = "") -> str:
    svg = render(source, "svg").decode()
    svg = svg[svg.index("<svg") :]
    if css_class:
        svg = re.sub(r'width="[\d.]+pt" height="[\d.]+pt"', f'class="{css_class}"', svg, count=1)
    return svg
