import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeFile } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";

export type WorkspaceRemoteStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceRemoteState {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
}

export function resolveWorkspaceRemoteUpdater<T>(
  previous: T,
  updater: WorkspaceRemoteStateUpdater<T>,
): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialWorkspaceRemoteState(): WorkspaceRemoteState {
  return {
    workspaceFiles: [],
    reeArtifactFiles: [],
    workspaceSourceState: {
      sourceAvailable: false,
      sourceIncluded: false,
      sourceAcquiredBy: "",
      uploadedArchive: "",
      sourceSnapshotArchive: "",
      sourceSnapshotCapturedAt: "",
    },
    artifactStatus: {
      runtimeIncluded: false,
      downloadableFiles: [],
      sealedAt: "",
      sealHash: "",
    },
    sourceSnapshotFiles: [],
    sourceSnapshotArchiveName: "",
  };
}
