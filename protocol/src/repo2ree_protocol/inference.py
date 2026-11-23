from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_protocol.command import ScriptTarget

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


DependencyKind = Literal[
    "source",
    "dependency_inventory",
    "script",
    "experiment_environment_artifact",
    "experiment_environment_declaration",
    "experiment_declaration",
    "baseline_result",
]


class CandidateDependency(BaseModel):
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


class ScriptValidation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["not_run", "not_runnable", "succeeded", "failed", "stale"]
    script_digest: str | None = None
    source_snapshot_digest: str | None = None
    experiment_environment_digest: str | None = None
    matching_run_id: str | None = None


class DockerExperimentEnvironmentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker_archive"] = "docker_archive"
    dockerfile_path: str
    build_context: str
    image_ref: str
    artifact_path: str


ExperimentEnvironmentPlan = DockerExperimentEnvironmentPlan


ContainerEngine = Literal["docker", "podman"]


class DockerExperimentEnvironmentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["docker_archive"] = "docker_archive"
    artifact_path: str
    image_ref: str
    engine: ContainerEngine | None = None
    workspace_mount: str = "/workspace"
    working_directory: str = "/workspace"


DEFAULT_VENV_RESTORE_DIR = "/tmp/ree-venv"  # noqa: S108


class VenvExperimentEnvironmentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["venv_archive"] = "venv_archive"
    artifact_path: str
    venv_restore_dir: str = DEFAULT_VENV_RESTORE_DIR
    interpreter: str = "python"


ExperimentEnvironmentContract = Annotated[
    DockerExperimentEnvironmentContract | VenvExperimentEnvironmentContract,
    Field(discriminator="kind"),
]


class ArgvCommandCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["argv"] = "argv"
    candidate_id: str
    argv: list[str]
    source: str


class ShellCommandCandidate(BaseModel):
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
    source: Literal["root", "wrapper"]


class DockerfileBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["dockerfile"] = "dockerfile"
    path: str
    build_context: str
    digest: str


class RequirementsProjectBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["requirements_project"] = "requirements_project"
    requirements_path: str
    digest: str
    hash_locked: bool


class ExperimentEnvironmentPlanBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment_environment_plan"] = "experiment_environment_plan"
    plan: ExperimentEnvironmentPlan


class ExperimentEnvironmentDeclarationBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment_environment_declaration"] = "experiment_environment_declaration"
    path: str
    digest: str | None = None


ExperimentEnvironmentContractProvenance = Literal["inspected_artifact", "unchanged_generated_build"]


class ExperimentEnvironmentContractBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment_environment_contract"] = "experiment_environment_contract"
    contract: ExperimentEnvironmentContract
    provenance: ExperimentEnvironmentContractProvenance


class ImageCommandBinding(BaseModel):
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
    | ExperimentEnvironmentPlanBinding
    | ExperimentEnvironmentDeclarationBinding
    | ExperimentEnvironmentContractBinding
    | ImageCommandBinding
    | ExperimentBinding
    | CommandCandidatesBinding,
    Field(discriminator="kind"),
]


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


class ExperimentEnvironmentContractObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment_environment_contract"] = "experiment_environment_contract"
    result: str
    experiment_environment_kind: str | None = None
    provenance: str | None = None
    detail: str = ""


class CommandCandidatesObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["command_candidates"] = "command_candidates"
    count: int
    sources: list[str] = Field(default_factory=list)


class ExperimentGateObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["experiment_gate"] = "experiment_gate"
    result: str
    requested: str = ""
    declared: bool = False


EngineState = Literal["absent", "unreachable", "usable"]


class EngineObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: ContainerEngine
    state: EngineState
    client_path: str | None = None
    server: str | None = None
    version: str | None = None
    rootless: bool | None = None
    detail: str | None = None


class ContainerEnginesProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["probed", "failed", "not_probed"]
    engines: list[EngineObservation] = Field(default_factory=list)
    detail: str = ""


class ContainerEnginesObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["container_engines"] = "container_engines"
    engine: ContainerEngine
    probe: ContainerEnginesProbe


SlurmState = Literal["absent", "unreachable", "usable"]


class SlurmPartition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    default: bool = False
    time_limit: str | None = None


class SlurmProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["probed", "failed", "not_probed"]
    state: SlurmState | None = None
    srun_path: str | None = None
    version: str | None = None
    partitions: list[SlurmPartition] = Field(default_factory=list)
    detail: str = ""


class SlurmObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["slurm"] = "slurm"
    probe: SlurmProbe


DecisionObservation = Annotated[
    LogicalRootObservation
    | PathMatchesObservation
    | StrategyOutcomesObservation
    | ExperimentEnvironmentContractObservation
    | CommandCandidatesObservation
    | ExperimentGateObservation
    | ContainerEnginesObservation
    | SlurmObservation,
    Field(discriminator="kind"),
]


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
    source_snapshot_digest: str | None = None
    engine: InferenceEngineInfo
    results: list[TargetInferenceResult] = Field(default_factory=list)
    dags: list[DecisionDag] = Field(default_factory=list)
