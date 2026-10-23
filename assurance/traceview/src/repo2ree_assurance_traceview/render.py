"""Render an behaviour trace into its self-contained HTML page."""

from __future__ import annotations

from repo2ree_assurance_traceview.model import BehaviourTrace

PLACEHOLDER = "/*TRACE*/null"


def render_html(trace: BehaviourTrace, template: str) -> str:
    if PLACEHOLDER not in template:
        raise ValueError(f"template has no {PLACEHOLDER} placeholder")
    # Any "<" in a label could end or derail the inline script ("</script>", "<!--<script>").
    # JSON only has "<" inside strings, where the escape means the same.
    data = trace.model_dump_json().replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, data)
