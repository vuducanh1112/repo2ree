"""Behaviour traces of recorded repo2ree behaviour, drawn from a verification.

The checker (``repo2ree_assurance_checker``) owns the only model of what happened: its replayed evidence
and verdicts. This package groups that model into operations, follows each one across components,
traces a sealed REE's provenance, and attaches OpenTelemetry spans as context. Spans never change a verdict
or an order. It is used through its command line (``python -m repo2ree_assurance_traceview``).
"""
