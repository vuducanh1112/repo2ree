"""The workbench service: the process resident inside one execution environment.

It dials the control plane on an execution-only socket, enrolls against the
allocation it was started for, and runs REE commands as short-lived executor
processes against one configured root.

``connection`` owns the socket and the in-flight request table, ``dispatcher``
turns validated requests into ``service`` calls, ``transfers`` holds chunked
copy-in state, and ``app`` composes the process.

Nothing here creates, replaces, or destroys an environment — that is the
provider's job, and the root pyproject's import contracts enforce the split.
"""
