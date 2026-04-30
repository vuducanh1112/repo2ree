import type { ReeFile } from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";

export type WorkspaceRemoteStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceRemoteState {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
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
    sourceSnapshotFiles: [],
    sourceSnapshotArchiveName: "",
  };
}
