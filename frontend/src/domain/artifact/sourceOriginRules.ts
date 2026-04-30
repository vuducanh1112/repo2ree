import type { Ree } from "../ree/ReeSpec";
import { splitLegacyReeModel, toLegacyReeViewModel } from "../ree/reeLegacyAdapters";

export function enforceSourceOriginRules(ree: Ree): Ree {
  const split = splitLegacyReeModel(ree);
  const hasDownloadedSource =
    !!split.workspaceSourceState._sourceAvailable &&
    split.workspaceSourceState._sourceAcquiredBy === "download";
  const hasUploadedSource =
    !!split.workspaceSourceState._sourceAvailable &&
    split.workspaceSourceState._sourceAcquiredBy === "upload";

  const nextSpec =
    !hasDownloadedSource && split.reeSpec.origin_url
      ? { ...split.reeSpec, origin_url: "" }
      : split.reeSpec;
  const nextWorkspaceSourceState =
    hasUploadedSource && !split.workspaceSourceState._sourceIncluded
      ? { ...split.workspaceSourceState, _sourceIncluded: true }
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
