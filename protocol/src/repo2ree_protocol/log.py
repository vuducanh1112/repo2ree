"""Log-streaming contract shared by both sides of the command boundary.

A workbench executes a Command and streams log events back to the host as
it runs. ``LogSink`` is the host-side callback those events are delivered
to — ``(stream, level, message)``, e.g. ``("stdout", "info", "…")``. It
lives in ``protocol`` because both the execution plane (core handlers,
which emit) and the control plane (the supervisor, which relays) speak it.
"""

from __future__ import annotations

from collections.abc import Callable

LogSink = Callable[[str, str, str], None]
