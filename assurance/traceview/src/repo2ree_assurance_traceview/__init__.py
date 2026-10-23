"""Operation-level views of recorded repo2ree behaviour.

The checker (``repo2ree_assurance_checker``) owns the only model of what happened: its replayed evidence
and verdicts. This package groups that model into operations, follows each one across components,
traces a sealed REE's provenance, and attaches OpenTelemetry spans as context. Spans never change a verdict or an order.
"""

from repo2ree_assurance_traceview.model import BehaviourTrace
from repo2ree_assurance_traceview.operations import build_trace, rees
from repo2ree_assurance_traceview.provenance import Provenance, build_provenance, render_text
from repo2ree_assurance_traceview.render import render_html
from repo2ree_assurance_traceview.spans import Span, SpanIndex, parse_spans

__all__ = [
    "BehaviourTrace",
    "Provenance",
    "Span",
    "SpanIndex",
    "build_provenance",
    "build_trace",
    "parse_spans",
    "rees",
    "render_html",
    "render_text",
]
