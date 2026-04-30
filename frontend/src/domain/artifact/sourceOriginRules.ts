import type { ReeDraftViewModel } from "../ree/ReeSpec";
import { splitLegacyReeModel, toLegacyReeViewModel } from "../ree/reeLegacyAdapters";

export function enforceSourceOriginRules(ree: ReeDraftViewModel): ReeDraftViewModel {
  const split = splitLegacyReeModel(ree);
  const hasDownloadedSource =
    !!split.workspaceSourceState.sourceAvailable &&
    split.workspaceSourceState.sourceAcquiredBy === "download";
  const hasUploadedSource =
    !!split.workspaceSourceState.sourceAvailable &&
    split.workspaceSourceState.sourceAcquiredBy === "upload";

  const nextSpec =
    !hasDownloadedSource && split.reeSpec.origin_url
      ? { ...split.reeSpec, origin_url: "" }
      : split.reeSpec;
  const nextWorkspaceSourceState =
    hasUploadedSource && !split.workspaceSourceState.sourceIncluded
      ? { ...split.workspaceSourceState, sourceIncluded: true }
      : split.workspaceSourceState;

  if (nextSpec === split.reeSpec && nextWorkspaceSourceState === split.workspaceSourceState) {
    return ree;
  }

  return toLegacyReeViewModel({
    reeSpec: nextSpec,
    workspaceSourceState: nextWorkspaceSourceState,
    artifactStatus: split.artifactStatus,
    evaluationState: split.evaluationState,
  });
}
