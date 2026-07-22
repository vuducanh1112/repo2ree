"""Typed model surface for script inference.

Everything the engine, checks, resolvers, renderers, decision graphs, and the
envelope handler exchange lives here so the closed discriminated unions
(bindings, observations, decision nodes) have a single definition and no import
cycle forms between the machinery modules.

The load-bearing rule of this design is that the *published, versioned decision
DAG is the only control-flow authority* (see ``ignore/script-inference-design.md``).
These models are the data that DAG is built from and the trace it emits; there
is no parallel imperative rule implementation.
"""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

# ================================================
# Targets
# ================================================

TargetKind = Literal[
    "build",
    "activation_run",
    "activation_verify",
    "experiment_run",
    "experiment_verify",
]


class ScriptTargetSelector(BaseModel):
    """What a caller asks inference about: a kind, no path.

    The server resolves the reserved path from the kind (and, for experiments,
    the reserved slug convention); a caller cannot redirect inference at an
    arbitrary workspace file.
    """

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None


class ScriptTarget(BaseModel):
    """A resolved executable target. ``path`` is output-only."""

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None
    path: str


# ================================================
# Status / application policy
# ================================================

CandidateStatus = Literal[
    "complete",
    "needs_input",
    "not_inferred",
]

ApplicationPolicy = Literal[
    "automatic_allowed",
    "confirmation_required",
    "unavailable",
]


# ================================================
# Evidence, warnings, dependencies
# ================================================

DependencyKind = Literal[
    "source",
    "dependency_inventory",
    "script",
    "runtime_artifact",
    "runtime_declaration",
    "experiment_declaration",
    "baseline_result",
]


class CandidateDependency(BaseModel):
    """Exactly which evidence justifies a candidate — the staleness key."""

    model_config = ConfigDict(extra="forbid")

    kind: DependencyKind
    path: str | None = None
    digest: str
    role: str


class InferenceEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    path: str | None = None
    digest: str | None = None
    line: int | None = None
    detail: str


WarningSeverity = Literal["info", "warning", "error"]


class InferenceWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: WarningSeverity
    blocking: bool
    message: str
    affected_paths: list[str] = Field(default_factory=list)
    details: dict[str, object] | None = None


# ================================================
# Validation
# ================================================


class ScriptValidation(BaseModel):
    """Execution validation of a *written* script — distinct from inference.

    For a candidate that has not been written, ``script_digest`` is the
    candidate's own byte digest and ``status`` is ``not_run``; the other digests
    stay absent until a real run produces a receipt.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["not_run", "not_runnable", "succeeded", "failed", "stale"]
    script_digest: str | None = None
    source_snapshot_digest: str | None = None
    runtime_digest: str | None = None
    matching_run_id: str | None = None


# ================================================
# Runtime plans / contracts (rendering evidence, not executable state)
# ================================================


class DockerRuntimePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker_archive"] = "docker_archive"
    dockerfile_path: str
    build_context: str
    image_ref: str
    artifact_path: str


# Phase 1 has one plan type; later phases widen this to a kind-discriminated
# union of explicit plan models.
RuntimePlan = DockerRuntimePlan


class DockerRuntimeContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker_archive"] = "docker_archive"
    artifact_path: str
    image_ref: str
    workspace_mount: str = "/workspace"
    working_directory: str = "/workspace"


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
    "experiment",
    "command_candidates",
    "verification_claim",
]


class ProjectRootBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["project_root"] = "project_root"
    path: str
    # "root" when resolve_logical_root() returned "."; "wrapper" when it peeled
    # one or more wrapper directories. The resolver does not know *why* a wrapper
    # exists (clone vs archive), only that it does.
    source: Literal["root", "wrapper"]


class DockerfileBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["dockerfile"] = "dockerfile"
    path: str
    build_context: str
    digest: str


class RequirementsProjectBinding(BaseModel):
    """A pip ``requirements.txt`` shape at the logical project root.

    Carries only the located file and its digest — the base image travels via
    deployment policy, not repository evidence, so it is resolved by the
    base-image check/renderer rather than baked into this binding.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["requirements_project"] = "requirements_project"
    requirements_path: str
    digest: str


class RuntimePlanBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["runtime_plan"] = "runtime_plan"
    plan: RuntimePlan


class RuntimeDeclarationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["runtime_declaration"] = "runtime_declaration"
    path: str
    digest: str | None = None


DecisionBinding = Annotated[
    ProjectRootBinding
    | DockerfileBinding
    | RequirementsProjectBinding
    | RuntimePlanBinding
    | RuntimeDeclarationBinding,
    Field(discriminator="kind"),
]


# ================================================
# Observations — closed, discriminated, safe-to-display trace payloads
# ================================================


class LogicalRootObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["logical_root"] = "logical_root"
    path: str
    wrapper_depth: int


class PathMatchesObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["path_matches"] = "path_matches"
    count: int
    paths: list[str]


class StrategyOutcomeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    outcome: Literal["complete", "candidate", "blocked", "not_applicable"]
    leaf: str


class StrategyOutcomesObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["strategy_outcomes"] = "strategy_outcomes"
    outcomes: list[StrategyOutcomeObservation]


DecisionObservation = Annotated[
    LogicalRootObservation | PathMatchesObservation | StrategyOutcomesObservation,
    Field(discriminator="kind"),
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


@runtime_checkable
class Check(Protocol):
    code: str
    label: str
    branches: frozenset[str]
    requires: frozenset[BindingKind]
    produces: dict[str, frozenset[BindingKind]]

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


# ================================================
# Candidates and per-target results
# ================================================


class ScriptCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    target: ScriptTarget
    status: CandidateStatus
    application: ApplicationPolicy
    body: str | None
    dependencies: list[CandidateDependency] = Field(default_factory=list)
    evidence: list[InferenceEvidence] = Field(default_factory=list)
    warnings: list[InferenceWarning] = Field(default_factory=list)
    inference_rule: str
    inference_version: int
    decision_leaf: str
    validation: ScriptValidation


# ================================================
# Decision DAG node schema (deployment-static, versioned data)
# ================================================


class CheckNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["check"] = "check"
    check: str
    branches: dict[str, str]


class ForkNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["fork"] = "fork"
    branches: dict[str, str]
    join: str


class StrategyLeafNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["strategy_leaf"] = "strategy_leaf"
    strategy: str
    outcome: Literal["complete", "candidate", "blocked", "not_applicable"]
    rule: str | None = None
    inference_version: int = 1
    warnings: list[str] = Field(default_factory=list)
    render: str | None = None
    next: str


class ResolveNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["resolve"] = "resolve"
    fork: str
    resolver: str
    branches: dict[str, str]


class ResultNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: Literal["result"] = "result"
    status: CandidateStatus
    application: ApplicationPolicy


DecisionNode = Annotated[
    CheckNode | ForkNode | StrategyLeafNode | ResolveNode | ResultNode,
    Field(discriminator="kind"),
]


class DecisionDag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    version: int
    root: str
    nodes: list[DecisionNode]

    def node(self, node_id: str) -> DecisionNode:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(node_id)


# ================================================
# Decision trace — the walk is the decision *and* the explanation
# ================================================


class DecisionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    kind: Literal["check", "fork", "strategy_leaf", "resolve", "result"]
    check: str | None = None
    branch: str | None = None
    observed: DecisionObservation | None = None
    outcome: str | None = None
    bindings: tuple[DecisionBinding, ...] = ()
    evidence: list[InferenceEvidence] = Field(default_factory=list)


class TraversedEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    branch: str
    target: str


class DecisionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dag: str
    version: int
    steps: list[DecisionStep]
    edges: list[TraversedEdge]
    result_node: str


class TargetInferenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: ScriptTarget
    status: CandidateStatus
    application: ApplicationPolicy
    candidates: list[ScriptCandidate] = Field(default_factory=list)
    warnings: list[InferenceWarning] = Field(default_factory=list)
    decision: DecisionTrace


class InferenceEngineInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "repo2ree-script-inference"
    version: str


class InferenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    ree_id: str = ""
    # Passive provenance stamp: the receipt-chain root that already identifies
    # the acquired source. Nothing branches on it; inference computes no source
    # digest of its own.
    source_snapshot_digest: str | None = None
    engine: InferenceEngineInfo
    results: list[TargetInferenceResult] = Field(default_factory=list)
    # The static, versioned decision DAGs executed for the requested targets —
    # the full graph (all branches, not just the traversed path). A client
    # overlays each target's ``decision`` trace onto the matching DAG (by
    # ``key``) to show evaluated vs. unevaluated branches. Deduplicated by key.
    dags: list[DecisionDag] = Field(default_factory=list)


# Deferred imports resolved at module end to keep the union definitions above
# free of forward-reference clutter while avoiding an import cycle.
from repo2ree_core.script_inference.policy import InferencePolicy  # noqa: E402
from repo2ree_core.script_inference.repository_facts import RepositoryFacts  # noqa: E402

DecisionContext.model_rebuild()
StrategyOutcome.model_rebuild()
