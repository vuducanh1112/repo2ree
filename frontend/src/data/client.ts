import type { WorkspaceRuntimeValue } from "../app/browser/BrowserRuntime";

export function resolveWorkspaceId(runtime: WorkspaceRuntimeValue, workspaceId?: string): string {
  return workspaceId || runtime.workspaceId;
}
