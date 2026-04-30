import type { ReeDraftViewModel } from "../../domain/ree/ReeSpec";
import type { ReeFile } from "../../domain/ree/ReeTypes";

export interface LogLine {
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
  ts?: string;
}

export interface LogEntry {
  lines: LogLine[];
  ts: string;
}

export type WorkflowRunLogEntry = LogEntry;

export type WorkspaceResetMode = "download" | "upload" | "clear";

export interface WorkspaceResetPayload<TSourceType = string> {
  mode?: WorkspaceResetMode;
  source?: string;
  sourceType?: TSourceType;
  archiveName?: string;
  archiveContentBase64?: string;
}

export type WorkflowRunStatus =
  | "created"
  | "queued"
  | "provisioning"
  | "running"
  | "succeeded"
  | "failed"
  | "canceling"
  | "canceled";

export interface WorkflowRunRecord {
  runId: string;
  status: WorkflowRunStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface WorkflowRunLogChunk {
  lines: LogLine[];
  nextCursor?: string;
  hasMore: boolean;
}

export interface WorkspaceBinaryDownload {
  bytes: ArrayBuffer;
  fileName?: string;
}

export interface ReeProject<TFile = unknown> {
  id: string;
  files: TFile[];
  reeFiles?: ReeFile[];
  ree?: ReeDraftViewModel;
}

export function serializeWorkspaceResetPayload(payload: WorkspaceResetPayload): string {
  return JSON.stringify(payload);
}

export function parseWorkspaceResetPayload<TSourceType = string>(
  raw: string,
  fallbackSourceType: TSourceType,
): WorkspaceResetPayload<TSourceType> {
  try {
    return raw ? (JSON.parse(raw) as WorkspaceResetPayload<TSourceType>) : {};
  } catch {
    return { mode: "download", source: raw, sourceType: fallbackSourceType };
  }
}
