import type { ReeDraftViewModel } from "../ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeFile,
  Timestamps,
  WorkflowLogs,
  WorkflowParams,
} from "../ree/ReeTypes";
import type { FileTreeNode } from "./FileTree";

export interface WorkspaceSourceResetInput {
  ree: ReeDraftViewModel;
}

interface WorkspaceSourceResetFields {
  badges: Badges;
  timestamps: Timestamps;
  workflowLogs: WorkflowLogs;
  actionStates: ActionStates;
  workflowParams: WorkflowParams;
  ree: ReeDraftViewModel;
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
}

export function computeSourceChangeConsequences(
  workspace: WorkspaceSourceResetInput,
  workflowParams: WorkflowParams,
): WorkspaceSourceResetFields {
  return {
    badges: {},
    timestamps: {},
    workflowLogs: {},
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
    workspaceFiles: [],
    reeArtifactFiles: [],
    sourceSnapshotFiles: [],
    sourceSnapshotArchiveName: "",
  };
}
