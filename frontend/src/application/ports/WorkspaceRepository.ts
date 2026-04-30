import type { ReeProject, WorkspaceResetPayload } from "./repositoryTypes";

export interface WorkspaceRepository<TFile = unknown> {
  getWorkspace(id: string): Promise<ReeProject<TFile>>;
  updateFile(id: string, path: string, content: string): Promise<void>;
  updateReeDraft(id: string, reePatch: Record<string, unknown>): Promise<void>;
  deleteFile(id: string, path: string): Promise<void>;
  getFileBytes(id: string, path: string): Promise<ArrayBuffer>;
  resetWorkspaceRequest(id: string, request: WorkspaceResetPayload): Promise<void>;
}
