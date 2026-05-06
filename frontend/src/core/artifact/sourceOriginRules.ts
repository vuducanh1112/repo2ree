import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { ReeSpec } from "../ree/ReeSpec";
import type { EvaluationState } from "../review/EvaluationState";
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
  const hasUploadedSource =
    !!state.workspaceSourceState.sourceAvailable &&
    state.workspaceSourceState.sourceAcquiredBy === "upload";

  const nextReeSpec =
    !hasDownloadedSource && state.reeSpec.origin_url
      ? { ...state.reeSpec, origin_url: "" }
      : state.reeSpec;
  const nextWorkspaceSourceState =
    hasUploadedSource && !state.workspaceSourceState.sourceIncluded
      ? { ...state.workspaceSourceState, sourceIncluded: true }
      : state.workspaceSourceState;

  if (nextReeSpec === state.reeSpec && nextWorkspaceSourceState === state.workspaceSourceState) {
    return state;
  }

  return {
    reeSpec: nextReeSpec,
    workspaceSourceState: nextWorkspaceSourceState,
    artifactStatus: state.artifactStatus,
    evaluationState: state.evaluationState,
  };
}
