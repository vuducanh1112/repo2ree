export interface LogLine {
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
}

export interface LogEntry {
  lines: LogLine[];
  ts: string;
}

export type WorkspaceServiceLogEntry = LogEntry;

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

export interface ReeProject<TFile = unknown> {
  id: string;
  files: TFile[];
}

export interface IWorkspaceService<TFile = unknown> {
  getWorkspace(id: string): Promise<ReeProject<TFile>>;
  updateFile(id: string, path: string, content: string): Promise<void>;
  deleteFile?(id: string, path: string): Promise<void>;
  runScript(id: string, scriptKey: string): Promise<WorkspaceServiceLogEntry>;
  resetWorkspace(id: string, newSource: string): Promise<void>;
  resetWorkspaceRequest?: (id: string, request: WorkspaceResetPayload) => Promise<void>;
  startWorkflowRun?: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  getWorkflowRun?: (id: string, runId: string) => Promise<WorkflowRunRecord>;
  getWorkflowRunLogs?: (id: string, runId: string, cursor?: string) => Promise<WorkflowRunLogChunk>;
}

interface WorkspaceServiceDelegates<TFile = unknown> {
  getWorkspace: (id: string) => Promise<ReeProject<TFile>>;
  updateFile: (id: string, path: string, content: string) => Promise<void>;
  deleteFile?: (id: string, path: string) => Promise<void>;
  runScript: (id: string, scriptKey: string) => Promise<WorkspaceServiceLogEntry>;
  resetWorkspace: (id: string, newSource: string) => Promise<void>;
  resetWorkspaceRequest?: (id: string, request: WorkspaceResetPayload) => Promise<void>;
  startWorkflowRun?: (
    id: string,
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  getWorkflowRun?: (id: string, runId: string) => Promise<WorkflowRunRecord>;
  getWorkflowRunLogs?: (id: string, runId: string, cursor?: string) => Promise<WorkflowRunLogChunk>;
}

export function createDummyWorkspaceService<TFile = unknown>(
  delegates: WorkspaceServiceDelegates<TFile>,
): IWorkspaceService<TFile> {
  return {
    getWorkspace: delegates.getWorkspace,
    updateFile: delegates.updateFile,
    deleteFile: delegates.deleteFile,
    runScript: delegates.runScript,
    resetWorkspace: delegates.resetWorkspace,
    resetWorkspaceRequest: delegates.resetWorkspaceRequest,
    startWorkflowRun: delegates.startWorkflowRun,
    getWorkflowRun: delegates.getWorkflowRun,
    getWorkflowRunLogs: delegates.getWorkflowRunLogs,
  };
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
