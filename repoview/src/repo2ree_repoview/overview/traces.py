"""The behaviour traces the overview bundles, each given the way back into the overview.

A trace page is a document of its own, written beside the test that made it. It leaves a slot for
whoever shows it among other pages; the overview fills it with the link back to the assurance gate
and the overview's pages, as paths from where the trace sits in the bundle.
"""

from __future__ import annotations

import json
import os

from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.html import Page

# The slot a trace page leaves (repo2ree_assurance_traceview.render.CONTEXT_SLOT).
CONTEXT_SLOT = '<script type="application/json" id="context">null</script>'


def place_traces(bundle: Bundle, pages: list[Page]) -> int:
    """Fill the slot of every bundled trace page; how many were filled."""
    filled = 0
    for path in sorted(bundle.root.glob("evidence/*/tests/*/traces/*.html")):
        page = path.read_text(encoding="utf-8")
        if CONTEXT_SLOT not in page:
            continue
        up = os.path.relpath(bundle.root, path.parent).replace(os.sep, "/")
        context = {
            "back": {"title": "Assurance gate", "href": f"{up}/assurance-gate.html"},
            "nav": [
                {"title": "Overview", "href": f"{up}/index.html"},
                *({"title": item.title, "href": f"{up}/{item.slug}.html"} for item in pages),
            ],
        }
        # As the trace's own data: no "<" can end the script it sits in.
        data = json.dumps(context).replace("<", "\\u003c")
        slot = CONTEXT_SLOT.replace(">null<", f">{data}<")
        bundle.amend(path.relative_to(bundle.root).as_posix(), page.replace(CONTEXT_SLOT, slot, 1))
        filled += 1
    return filled
