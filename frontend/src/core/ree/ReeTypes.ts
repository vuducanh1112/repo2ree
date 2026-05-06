import type { ReeAssemblyOperationParams as ReeAssemblyOperationParamsShape } from "../ree-assembly/ReeAssemblyOperationParams";

export type Badges = Record<string, boolean>;
export type Timestamps = Record<string, string>;
export type ActionStates = Record<string, "loading" | "done">;
export type ExecutionRunLogs = Record<string, LogEntry>;
export type ReeAssemblyOperationParams = ReeAssemblyOperationParamsShape;

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
