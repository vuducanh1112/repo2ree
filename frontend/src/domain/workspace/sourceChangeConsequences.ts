import type { ActionStates, Badges, Timestamps, WorkflowParams } from "../ree/ReeTypes";
import type { ReeViewState } from "../ree/ReeViewState";

export interface WorkspaceSourceResetInput {
  ree: ReeViewState;
}

interface WorkspaceSourceResetFields {
  badges: Badges;
  timestamps: Timestamps;
  actionStates: ActionStates;
  workflowParams: WorkflowParams;
  ree: ReeViewState;
  sourceSnapshotArchiveName: string;
}

export function computeSourceChangeConsequences(
  workspace: WorkspaceSourceResetInput,
  workflowParams: WorkflowParams,
): WorkspaceSourceResetFields {
  return {
    badges: {},
    timestamps: {},
    actionStates: {},
    workflowParams,
    ree: {
      ...workspace.ree,
      origin_url: "",
      runtime: "",
      build_runtime_script: "",
      activation_script: "",
      sbom: "",
      swhid: "",
      detected_dependencies: "",
      repro_level: "",
      evalLevel: 0,
      sourceAvailable: false,
      sourceAcquiredBy: undefined,
      runtimeIncluded: false,
      zenodo_doi: "",
      uploadedArchive: "",
      sourceSnapshotArchive: "",
      sourceSnapshotCapturedAt: "",
    },
    sourceSnapshotArchiveName: "",
  };
}
