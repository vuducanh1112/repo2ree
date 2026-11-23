from __future__ import annotations

from typing import ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.command import ScriptTarget
from repo2ree_protocol.inference import (
    CandidateDependency,
    DecisionBinding,
    DecisionObservation,
    InferenceEvidence,
    InferenceWarning,
    ScriptCandidate,
    StrategyOutcomesObservation,
)

BindingKind = Literal[
    "project_root",
    "dockerfile",
    "requirements_project",
    "experiment_environment_plan",
    "experiment_environment_declaration",
    "experiment_environment_contract",
    "image_command",
    "experiment",
    "command_candidates",
    "verification_claim",
]


class DecisionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: RepositoryFacts
    policy: InferencePolicy
    ree_name: str = ""
    experiment_environment: ExperimentEnvironmentInputs = Field(default_factory=lambda: ExperimentEnvironmentInputs())
    machine: MachineInputs = Field(default_factory=lambda: MachineInputs())
    requested_experiment: str = ""
    bindings: tuple[DecisionBinding, ...] = ()

    def binding(self, kind: BindingKind) -> DecisionBinding | None:
        for binding in self.bindings:
            if binding.kind == kind:
                return binding
        return None

    def with_bindings(self, new: tuple[DecisionBinding, ...]) -> DecisionContext:
        if not new:
            return self
        present = {binding.kind for binding in self.bindings}
        for binding in new:
            if binding.kind in present:
                raise ValueError(f"conflicting binding of kind {binding.kind!r}")
            present.add(binding.kind)
        return self.model_copy(update={"bindings": self.bindings + tuple(new)})


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch: str
    observed: DecisionObservation
    bindings: tuple[DecisionBinding, ...] = ()
    evidence: list[InferenceEvidence] = Field(default_factory=list)
    warnings: list[InferenceWarning] = Field(default_factory=list)


@runtime_checkable
class Check(Protocol):
    code: str
    label: str
    branches: frozenset[str]
    requires: frozenset[BindingKind]
    produces: ClassVar[dict[str, frozenset[BindingKind]]]

    def evaluate(self, context: DecisionContext) -> CheckResult: ...


class RenderedScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    dependencies: list[CandidateDependency] = Field(default_factory=list)
    evidence: list[InferenceEvidence] = Field(default_factory=list)
    warnings: list[InferenceWarning] = Field(default_factory=list)


@runtime_checkable
class Renderer(Protocol):
    code: str
    requires: frozenset[BindingKind]

    def render(self, context: DecisionContext, target: ScriptTarget) -> RenderedScript: ...


class StrategyOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    leaf: str
    outcome: Literal["complete", "candidate", "blocked", "not_applicable"]
    bindings: tuple[DecisionBinding, ...] = ()
    candidate: ScriptCandidate | None = None
    warnings: list[InferenceWarning] = Field(default_factory=list)


class ResolverResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: str
    observed: StrategyOutcomesObservation


@runtime_checkable
class Resolver(Protocol):
    code: str
    results: frozenset[str]

    def evaluate(self, outcomes: dict[str, StrategyOutcome]) -> ResolverResult: ...


from repo2ree_core.author_recipes.inference.experiment_environment_inputs import ExperimentEnvironmentInputs  # noqa: E402
from repo2ree_core.author_recipes.inference.machine import MachineInputs  # noqa: E402
from repo2ree_core.author_recipes.inference.policy import InferencePolicy  # noqa: E402
from repo2ree_core.author_recipes.inference.repository_facts import RepositoryFacts  # noqa: E402

DecisionContext.model_rebuild()
StrategyOutcome.model_rebuild()
