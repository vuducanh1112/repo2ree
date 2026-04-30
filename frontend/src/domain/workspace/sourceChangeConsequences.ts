import type { Ree } from "../ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeFile,
  ServiceLogs,
  ServiceParams,
  Timestamps,
} from "../ree/ReeTypes";
import type { FileTreeNode } from "./FileTree";

export interface ExplorerSourceResetInput {
  ree: Ree;
}

interface ExplorerSourceResetFields {
  badges: Badges;
  timestamps: Timestamps;
  serviceLogs: ServiceLogs;
  actionStates: ActionStates;
  serviceParams: ServiceParams;
  ree: Ree;
  virtualFiles: FileTreeNode[];
  workspaceReeFiles: ReeFile[];
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
}

export function computeSourceChangeConsequences(
  explorer: ExplorerSourceResetInput,
  serviceParams: ServiceParams,
): ExplorerSourceResetFields {
  return {
    badges: {},
    timestamps: {},
    serviceLogs: {},
    actionStates: {},
    serviceParams,
    ree: {
      ...explorer.ree,
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
    virtualFiles: [],
    workspaceReeFiles: [],
    immutableSourceSnapshotFiles: [],
    immutableSourceSnapshotArchiveName: "",
  };
}
