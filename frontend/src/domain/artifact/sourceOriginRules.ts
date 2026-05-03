import type { ReeSpec } from "../ree/ReeSpec";
import type { ReeViewState } from "../ree/ReeViewState";
import { splitReeViewState, toReeViewState } from "../ree/ReeViewState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";

interface SourceOriginRuleInput {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
}

interface SourceOriginRuleResult {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
}

export function enforceSourceOriginRulesForSlices({
  reeSpec,
  workspaceSourceState,
}: SourceOriginRuleInput): SourceOriginRuleResult {
  const hasDownloadedSource =
    !!workspaceSourceState.sourceAvailable && workspaceSourceState.sourceAcquiredBy === "download";
  const hasUploadedSource =
    !!workspaceSourceState.sourceAvailable && workspaceSourceState.sourceAcquiredBy === "upload";

  const nextSpec =
    !hasDownloadedSource && reeSpec.origin_url ? { ...reeSpec, origin_url: "" } : reeSpec;
  const nextWorkspaceSourceState =
    hasUploadedSource && !workspaceSourceState.sourceIncluded
      ? { ...workspaceSourceState, sourceIncluded: true }
      : workspaceSourceState;

  return {
    reeSpec: nextSpec,
    workspaceSourceState: nextWorkspaceSourceState,
  };
}

export function enforceSourceOriginRules(ree: ReeViewState): ReeViewState {
  const split = splitReeViewState(ree);
  const next = enforceSourceOriginRulesForSlices({
    reeSpec: split.reeSpec,
    workspaceSourceState: split.workspaceSourceState,
  });

  if (next.reeSpec === split.reeSpec && next.workspaceSourceState === split.workspaceSourceState) {
    return ree;
  }

  return toReeViewState({
    reeSpec: next.reeSpec,
    workspaceSourceState: next.workspaceSourceState,
    artifactStatus: split.artifactStatus,
    evaluationState: split.evaluationState,
  });
}
