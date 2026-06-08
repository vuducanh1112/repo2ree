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

export interface ActionReceipt {
  receipt_id: string;
  operation: string;
  command?: Record<string, unknown>;
  action_digest: string;
  input_digest?: string | null;
  output_digest?: string | null;
  status: "succeeded" | "failed" | "canceled";
  exit_code: number;
  outputs?: Record<string, unknown>;
  started_at: string;
  finished_at: string;
  predecessor?: string | null;
  log_ref?: string | null;
}
