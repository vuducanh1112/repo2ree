import type { WorkflowServiceParams } from "./services";

export interface Ree {
  name: string;
  origin_url: string;
  source_type: "" | "git" | "hg" | "svn" | "cvs" | "bzr" | "tarball";
  runtime: string;
  build_runtime_script: string;
  activation_script: string;
  sbom: string;
  swhid: string;
  zenodo_doi?: string;
  dataverse_doi?: string;
  repro_level?: string;
  detected_dependencies?: string;
  hardware_description: Record<string, string>;
  _evalLevel?: number;
  _sealedAt?: string;
  _sealHash?: string;
  _sourceAvailable?: boolean;
  _sourceIncluded?: boolean;
  _sourceAcquiredBy?: "download" | "upload" | "";
  _uploadedArchive?: string;
  _sourceSnapshotArchive?: string;
  _sourceSnapshotCapturedAt?: string;
  _runtimeIncluded?: boolean;
}

export type Badges = Record<string, boolean>;
export type Timestamps = Record<string, string>;
export type ActionStates = Record<string, "loading" | "done">;
export type ServiceLogs = Record<string, LogEntry>;
export type ServiceParams = WorkflowServiceParams;

export interface LogLine {
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
  ts?: string;
}

export interface LogEntry {
  lines: LogLine[];
  ts: string;
}

export interface SourceUploadCommit {
  mode: "archive";
  archiveName?: string;
  archiveFile?: File;
}

export interface ReeFile {
  id: string;
  name: string;
  type: "file";
  tag?: string;
  content?: string;
  size?: number;
}

export interface ZipEntry {
  path: string;
  data: Uint8Array;
}
