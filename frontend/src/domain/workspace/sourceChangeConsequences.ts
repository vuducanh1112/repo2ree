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
      _evalLevel: 0,
      _sourceAvailable: false,
      _sourceAcquiredBy: undefined,
      _runtimeIncluded: false,
      zenodo_doi: "",
      _uploadedArchive: "",
      _sourceSnapshotArchive: "",
      _sourceSnapshotCapturedAt: "",
    },
    workspaceFiles: [],
    reeArtifactFiles: [],
    sourceSnapshotFiles: [],
    sourceSnapshotArchiveName: "",
  };
}
