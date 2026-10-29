"""The engine's own types for script inference: its context, the protocols its
checks, renderers, and resolvers implement, and what they hand each other. The
report it publishes, and the closed unions inside it, are
:mod:`repo2ree_protocol.inference`.

The load-bearing rule of this design is that the *published, versioned decision
DAG is the only control-flow authority* (see ``docs/engineering/explanation/script-inference.md``).
These models are the data that DAG is built from and the trace it emits; there
is no parallel imperative rule implementation.
"""

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

# ================================================
# Bindings — closed, discriminated typed dataflow along the DAG
# ================================================

BindingKind = Literal[
    "project_root",
    "dockerfile",
    "requirements_project",
    "runtime_plan",
    "runtime_declaration",
    "runtime_contract",
    "image_command",
    "experiment",
    "command_candidates",
    "verification_claim",
]


# ================================================
# Decision context and check / resolver / renderer contracts
# ================================================


class DecisionContext(BaseModel):
    """Immutable evaluation context: repository facts, deployment policy, and the
    typed bindings accumulated along the walk so far.

    The engine never mutates a context in place: appending a binding produces a
    new context (``with_bindings``), and at most one binding of each kind may
    exist on any path.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    facts: RepositoryFacts
    policy: InferencePolicy
    # The REE's declared name, used to derive a readable runtime image tag.
    ree_name: str = ""
    # Authored state that does not come from scanning ``upstream``: the declared
    # runtime path, experiment declarations, and access to the built artifact /
    # written build script. Empty for build inference, which needs none of it.
    runtime: RuntimeInputs = Field(default_factory=lambda: RuntimeInputs())
    # The experiment a run/verify experiment target names. Empty for build and
    # activation targets. Set per-target by ``infer_scripts`` because the name
    # lives on the target, not on the shared scan.
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
    # Warnings a check observes at evaluation time (e.g. a blocked runtime
    # contract). Unlike a strategy leaf's static warning codes, these depend on
    # what the check saw, so they ride on the result. The engine folds them into
    # the target's warning union along whatever path the walk takes.
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
    """A renderer's output: one self-contained script body plus the evidence
    trail that justifies it. Inference produces only the shell script — a
    generated recipe (a synthesized Dockerfile) is embedded inline in the body,
    never emitted as a second file."""

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


# Deferred imports resolved at module end to keep the union definitions above
# free of forward-reference clutter while avoiding an import cycle.
from repo2ree_core.author_recipes.inference.policy import InferencePolicy  # noqa: E402
from repo2ree_core.author_recipes.inference.repository_facts import RepositoryFacts  # noqa: E402
from repo2ree_core.author_recipes.inference.runtime_inputs import RuntimeInputs  # noqa: E402

DecisionContext.model_rebuild()
StrategyOutcome.model_rebuild()
