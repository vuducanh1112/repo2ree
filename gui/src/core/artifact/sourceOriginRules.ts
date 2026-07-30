import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { ReeSpec } from "../ree/ReeSpec";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";

interface SourceOriginRulesStateInput {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

interface SourceOriginRulesStateResult {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

export function enforceSourceOriginRules(
  state: SourceOriginRulesStateInput,
): SourceOriginRulesStateResult {
  const hasDownloadedSource =
    !!state.workspaceSourceState.sourceAvailable &&
    state.workspaceSourceState.sourceAcquiredBy === "download";

  const nextReeSpec =
    !hasDownloadedSource && state.reeSpec.originUrl
      ? { ...state.reeSpec, originUrl: "" }
      : state.reeSpec;

  if (nextReeSpec === state.reeSpec) {
    return state;
  }

  return {
    reeSpec: nextReeSpec,
    workspaceSourceState: state.workspaceSourceState,
    artifactStatus: state.artifactStatus,
    evaluationState: state.evaluationState,
  };
}
