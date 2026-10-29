from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.command import ScriptTarget

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


# The absolute path a repo2ree-built venv is created at (and therefore restored
# to, because a venv bakes absolute paths). The build renderer creates the venv
# here and the run scaffolds restore it here; both import this one literal so the
# build/restore locations can never silently drift apart. A literal for the
# generated shell, not a temp path this process opens.
DEFAULT_VENV_RESTORE_DIR = "/tmp/ree-venv"  # noqa: S108


class VenvRuntimeContract(BaseModel):
    """A packed Python virtual environment as the runtime substrate.

    The build packs the venv as a gzipped tarball at ``artifact_path``; a
    runnable restores it to ``venv_restore_dir`` (an absolute path, because a
    venv bakes absolute paths and must be restored where it was built) and runs
    the command with that venv's ``bin`` on ``PATH``. There is no image ref: the
    workbench base image is the environment. ``venv_restore_dir`` defaults to the
    path a repo2ree build packs; an inspected artifact overrides it with the path
    recovered from the venv's own ``pyvenv.cfg``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["venv_archive"] = "venv_archive"
    artifact_path: str
    venv_restore_dir: str = DEFAULT_VENV_RESTORE_DIR
    interpreter: str = "python"


RuntimeContract = Annotated[
    DockerRuntimeContract | VenvRuntimeContract,
    Field(discriminator="kind"),
]


# ================================================
# Command candidates — runnable commands *suggested* to the author, never
# auto-selected in Phase 1. Rendered as commented `set --` examples.
# ================================================


class ArgvCommandCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["argv"] = "argv"
    candidate_id: str
    argv: list[str]
    source: str


class ShellCommandCandidate(BaseModel):
    """A shell-form command (e.g. a Docker shell-form ENTRYPOINT/CMD). It is
    never rewritten into guessed argv; the author must make the shell dependency
    explicit (``set -- sh -c '...'``)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["shell"] = "shell"
    candidate_id: str
    command: str
    shell: str = "sh"
    source: str


ScriptCommandCandidate = Annotated[
    ArgvCommandCandidate | ShellCommandCandidate,
    Field(discriminator="kind"),
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


RuntimeContractProvenance = Literal["inspected_artifact", "unchanged_generated_build"]


class RuntimeContractBinding(BaseModel):
    """A resolved, non-executable runtime contract plus how it was established.

    ``inspected_artifact`` inspected the built artifact itself;
    ``unchanged_generated_build`` reused the constants of a still-unedited
    inference-generated build script. Downstream renderers copy the contract's
    values as explicit literals.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["runtime_contract"] = "runtime_contract"
    contract: RuntimeContract
    provenance: RuntimeContractProvenance


class ImageCommandBinding(BaseModel):
    """The runtime image's declared command (Entrypoint/Cmd), parsed once when
    the artifact is inspected and carried forward so the command-candidate check
    need not re-open the (possibly multi-hundred-MB) archive. Absent when the
    contract came from an unchanged generated build (no artifact to inspect); the
    exec/shell forms are mutually exclusive, matching what inspection reports."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["image_command"] = "image_command"
    argv: list[str] | None = None
    shell_command: str | None = None


class ExperimentBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment"] = "experiment"
    name: str
    run_script_path: str
    verify_script_path: str | None = None
    output_paths: list[str] = Field(default_factory=list)


class CommandCandidatesBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["command_candidates"] = "command_candidates"
    candidates: list[ScriptCommandCandidate] = Field(default_factory=list)


DecisionBinding = Annotated[
    ProjectRootBinding
    | DockerfileBinding
    | RequirementsProjectBinding
    | RuntimePlanBinding
    | RuntimeDeclarationBinding
    | RuntimeContractBinding
    | ImageCommandBinding
    | ExperimentBinding
    | CommandCandidatesBinding,
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


class RuntimeContractObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["runtime_contract"] = "runtime_contract"
    # The check's outcome branch (e.g. "docker_single_ref", "missing", "valid").
    result: str
    runtime_kind: str | None = None
    provenance: str | None = None
    detail: str = ""


class CommandCandidatesObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["command_candidates"] = "command_candidates"
    count: int
    sources: list[str] = Field(default_factory=list)


class ExperimentGateObservation(BaseModel):
    """The experiment-declaration gate's outcome, for the decision trace."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment_gate"] = "experiment_gate"
    # The check's branch: "found" or "absent".
    result: str
    # The experiment name requested on the target (empty when none was set).
    requested: str = ""
    # Whether that name matched a declared REE experiment.
    declared: bool = False


DecisionObservation = Annotated[
    LogicalRootObservation
    | PathMatchesObservation
    | StrategyOutcomesObservation
    | RuntimeContractObservation
    | CommandCandidatesObservation
    | ExperimentGateObservation,
    Field(discriminator="kind"),
]


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
