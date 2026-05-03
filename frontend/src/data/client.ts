import type { ApiRuntimeValue } from "./apiRuntime";

export function resolveWorkspaceId(runtime: ApiRuntimeValue, workspaceId?: string): string {
  return workspaceId || runtime.workspaceId;
}

export async function ensureWorkspaceId(
  runtime: ApiRuntimeValue,
  workspaceId?: string,
): Promise<string> {
  return runtime.ensureWorkspaceId(resolveWorkspaceId(runtime, workspaceId));
}
