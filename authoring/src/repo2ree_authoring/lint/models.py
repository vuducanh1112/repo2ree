"""Models exchanged by script-lint rules, runners, and handlers."""

from __future__ import annotations

from dataclasses import dataclass

from repo2ree_authoring.lint.shellwords import ScriptWords
from repo2ree_protocol.command import ScriptTarget
from repo2ree_protocol.lint import ScriptDeclarations


@dataclass(frozen=True)
class ScriptContext:
    """What a contract rule sees. Internal: it never crosses the wire."""

    target: ScriptTarget
    source: str
    words: ScriptWords
    declarations: ScriptDeclarations

    @property
    def path(self) -> str:
        return self.target.path
