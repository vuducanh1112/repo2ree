export type SourceAcquiredBy = "download" | "upload" | "";

export interface WorkspaceSourceState {
  _sourceAvailable?: boolean;
  _sourceIncluded?: boolean;
  _sourceAcquiredBy?: SourceAcquiredBy;
  _uploadedArchive?: string;
  _sourceSnapshotArchive?: string;
  _sourceSnapshotCapturedAt?: string;
}
