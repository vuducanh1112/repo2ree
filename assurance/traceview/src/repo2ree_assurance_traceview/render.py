"""Render an behaviour trace into its self-contained HTML page."""

from __future__ import annotations

from repo2ree_assurance_traceview.model import BehaviourTrace

PLACEHOLDER = "/*TRACE*/null"


def render_html(trace: BehaviourTrace, template: str) -> str:
    if PLACEHOLDER not in template:
        raise ValueError(f"template has no {PLACEHOLDER} placeholder")
    # "</" would end the inline script early if a label ever contained it.
    data = trace.model_dump_json().replace("</", "<\\/")
    return template.replace(PLACEHOLDER, data)
