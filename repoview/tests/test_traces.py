"""A bundled trace page leads back into the overview, and the manifest records it as it is then."""

from __future__ import annotations

import json
import re
from pathlib import Path

from repo2ree_repoview.overview.bundle import Bundle, Origin, sha256
from repo2ree_repoview.overview.html import Page
from repo2ree_repoview.overview.traces import CONTEXT_SLOT, place_traces

TRACE = "evidence/run-1/tests/test-one/traces/dossier.html"


def test_a_bundled_trace_is_given_the_way_back_and_the_overviews_pages(tmp_path: Path) -> None:
    source = tmp_path / "dossier.html"
    source.write_text(f"<html><body>{CONTEXT_SLOT}<script>const TRACE = {{}};</script></body></html>")
    bundle = Bundle(tmp_path / "overview", "a" * 40)
    bundle.copy(source, TRACE, Origin(run="run-1"))
    (bundle.root / "evidence/run-1/tests/test-one/traces/untouched.html").write_text("<p>no slot</p>")

    assert place_traces(bundle, [Page("assurance-gate", "Assurance gate", "", ""), Page("zones", "Zones", "", "")]) == 1

    page = (bundle.root / TRACE).read_text()
    filled = re.search(r'<script type="application/json" id="context">(.*?)</script>', page)
    assert filled is not None
    context = json.loads(filled.group(1))
    assert context["back"] == {"title": "Assurance gate", "href": "../../../../../assurance-gate.html"}
    assert [item["href"] for item in context["nav"]] == [
        "../../../../../index.html",
        "../../../../../assurance-gate.html",
        "../../../../../zones.html",
    ]
    # Each link resolves to a page at the bundle's root.
    assert (bundle.root / TRACE).parent.joinpath(context["back"]["href"]).resolve() == (
        bundle.root / "assurance-gate.html"
    ).resolve()
    (copied,) = bundle.copied
    assert copied.sha256 == sha256(bundle.root / TRACE)
