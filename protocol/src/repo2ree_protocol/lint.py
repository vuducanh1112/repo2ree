from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_protocol.command import ScriptTarget
from repo2ree_ree.model import ReeDefinition

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

    experiment_environment_path: str | None = None

    @classmethod
    def from_definition(cls, definition: ReeDefinition | None) -> ScriptDeclarations:
        """Project a persisted definition into the view the rules read."""
        build_experiment_environment = definition.experiment_environment if definition else None
        experiment_environment_path = (
            build_experiment_environment.artifact_path if build_experiment_environment else None
        )
        return cls(
            experiment_environment_path=str(experiment_environment_path) if experiment_environment_path else None
        )
