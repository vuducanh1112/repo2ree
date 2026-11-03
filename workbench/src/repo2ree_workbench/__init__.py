"""The workbench service: the process that serves a store of REEs on one machine.

It dials the control plane on an execution-only socket, is admitted with its
store's token, and runs each REE's commands as short-lived executor processes
against that REE's directory in the store; the author's scripts run on the
machine or in a container from the REE's image.

``connection`` owns the socket and the in-flight request table, ``dispatcher``
turns validated requests into ``service`` calls, ``transfers`` holds chunked
copy-in state, and ``app`` composes the process.
"""
