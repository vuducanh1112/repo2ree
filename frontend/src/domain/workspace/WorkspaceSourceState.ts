export type SourceAcquiredBy = "download" | "upload" | "";

export interface WorkspaceSourceState {
  sourceAvailable?: boolean;
  sourceIncluded?: boolean;
  sourceAcquiredBy?: SourceAcquiredBy;
  uploadedArchive?: string;
  sourceSnapshotArchive?: string;
  sourceSnapshotCapturedAt?: string;
}
