export type WorkspaceResetMode = "download" | "upload" | "clear";

export interface WorkspaceResetPayload<TSourceType = string> {
  mode?: WorkspaceResetMode;
  source?: string;
  sourceType?: TSourceType;
  /** Git revision (commit, branch, or tag) to pin the fetch to; blank means default-branch HEAD. */
  revision?: string;
  archiveName?: string;
  archiveContentBase64?: string;
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
