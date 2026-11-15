"""The entry into the working environment an REE declares, on the machine a command runs on."""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.execution.working_environment import Entry, Machine
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.frames import LogSink
from repo2ree_ree.working_environment import WorkingEnvironmentObservation


class ReeEntry:
    """Enters the working environment the REE at ``layout`` declares, read when a step first enters it.

    A command that runs no script never reads it; one that does reads the declaration as it stands then, and the
    image the REE carries, when its bundle carries one.
    """

    def __init__(self, machine: Machine, layout: ReeLayout) -> None:
        self._machine = machine
        self._layout = layout
        self._entry: Entry | None = None

    def _resolved(self) -> Entry:
        if self._entry is None:
            store = ReeDirectory(self._layout)
            declared = store.read_ree().subject.definition.working_environment if store.manifest_exists() else None
            archive = self._layout.working_environment_archive
            self._entry = self._machine.enter(declared, bundled=archive if archive.is_file() else None)
        return self._entry

    def prepare(self, log: LogSink) -> None:
        self._resolved().prepare(log)

    def command(self, workspace: Path, argv: list[str]) -> list[str]:
        return self._resolved().command(workspace, argv)

    def finish(self, workspace: Path, log: LogSink) -> None:
        self._resolved().finish(workspace, log)

    def observe(self) -> WorkingEnvironmentObservation:
        return self._resolved().observe()
