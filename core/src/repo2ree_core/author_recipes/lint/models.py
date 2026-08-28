"""Models exchanged by script-lint rules, runners, and handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.author_recipes.lint.shellwords import ScriptWords
from repo2ree_core.author_recipes.targets import ScriptTarget
from repo2ree_core.domain.ree.model import ReeDefinition

FindingTier = Literal["syntax", "shell", "contract"]

FindingSeverity = Literal["info", "warning", "error"]


class Finding(BaseModel):
    """One observation about one script."""

    model_config = ConfigDict(extra="forbid")

    code: str
    tier: FindingTier
    severity: FindingSeverity
    blocking: bool
    message: str
    path: str
    line: int | None = None
    column: int | None = None
    detail: str | None = None


class TierStatus(BaseModel):
    """Whether an optional analysis tier ran."""

    model_config = ConfigDict(extra="forbid")

    tier: FindingTier
    status: Literal["ran", "unavailable"]
    tool: str | None = None
    tool_version: str | None = None
    detail: str | None = None


class LintReport(BaseModel):
    """Everything one lint run observed about one script."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    engine_version: str
    target: ScriptTarget
    findings: tuple[Finding, ...] = ()
    tiers: tuple[TierStatus, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether the report contains no blocking finding."""
        return not any(finding.blocking for finding in self.findings)


class ScriptDeclarations(BaseModel):
    """The narrow declaration view consumed by contract rules."""

    model_config = ConfigDict(extra="forbid")

    runtime_path: str | None = None

    @classmethod
    def from_definition(cls, definition: ReeDefinition | None) -> ScriptDeclarations:
        """Project a persisted definition into the view the rules read."""
        build_runtime = definition.build_runtime if definition else None
        runtime_path = build_runtime.runtime_path if build_runtime else None
        return cls(runtime_path=str(runtime_path) if runtime_path else None)


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
