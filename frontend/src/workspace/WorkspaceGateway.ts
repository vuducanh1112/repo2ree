import type { Ree, ReeFile } from "../types";

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
  ree?: Ree;
}

export interface WorkspaceGateway<TFile = unknown> {
  getWorkspace(id: string): Promise<ReeProject<TFile>>;
  updateFile(id: string, path: string, content: string): Promise<void>;
  updateReeDraft?(id: string, reePatch: Record<string, unknown>): Promise<void>;
  deleteFile?(id: string, path: string): Promise<void>;
  getFileBytes?(id: string, path: string): Promise<ArrayBuffer>;
  getReeArchive?(id: string): Promise<WorkspaceBinaryDownload>;
  runScript(id: string, scriptKey: string): Promise<WorkflowRunLogEntry>;
  resetWorkspace(id: string, newSource: string): Promise<void>;
  resetWorkspaceRequest?: (id: string, request: WorkspaceResetPayload) => Promise<void>;
  startWorkflowRun?: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  getWorkflowRun?: (id: string, runId: string) => Promise<WorkflowRunRecord>;
  getWorkflowRunLogs?: (id: string, runId: string, cursor?: string) => Promise<WorkflowRunLogChunk>;
  cancelWorkflowRun?: (id: string, runId: string) => Promise<WorkflowRunStatus>;
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
