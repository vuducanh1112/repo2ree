export interface LogLine {
  type: "info" | "ok" | "warn" | "err" | "out";
  msg: string;
}

export interface LogEntry {
  lines: LogLine[];
  ts: string;
}

export type WorkspaceServiceLogEntry = LogEntry;

export interface ReeProject<TFile = unknown> {
  id: string;
  files: TFile[];
}

export interface IWorkspaceService<TFile = unknown> {
  getWorkspace(id: string): Promise<ReeProject<TFile>>;
  updateFile(id: string, path: string, content: string): Promise<void>;
  runScript(id: string, scriptKey: string): Promise<WorkspaceServiceLogEntry>;
  resetWorkspace(id: string, newSource: string): Promise<void>;
}

interface WorkspaceServiceDelegates<TFile = unknown> {
  getWorkspace: (id: string) => Promise<ReeProject<TFile>>;
  updateFile: (id: string, path: string, content: string) => Promise<void>;
  runScript: (id: string, scriptKey: string) => Promise<WorkspaceServiceLogEntry>;
  resetWorkspace: (id: string, newSource: string) => Promise<void>;
}

export function createDummyWorkspaceService<TFile = unknown>(
  delegates: WorkspaceServiceDelegates<TFile>,
): IWorkspaceService<TFile> {
  return {
    getWorkspace: delegates.getWorkspace,
    updateFile: delegates.updateFile,
    runScript: delegates.runScript,
    resetWorkspace: delegates.resetWorkspace,
  };
}
