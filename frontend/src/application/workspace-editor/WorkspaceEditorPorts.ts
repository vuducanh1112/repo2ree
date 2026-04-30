export interface WorkspaceEditorClock {
  nowIso(): string;
  nowMillis(): number;
}

export interface WorkspaceEditorRandom {
  hex(length: number): string;
  int(minInclusive: number, maxInclusive: number): number;
}

export interface WorkspaceEditorBrowserDownloads {
  downloadBlob(bytes: BlobPart, options: { fileName: string; mimeType: string }): void;
}

export interface WorkspaceEditorRuntimePorts {
  clock: WorkspaceEditorClock;
  random: WorkspaceEditorRandom;
  sleep(ms: number): Promise<void>;
  browserDownloads: WorkspaceEditorBrowserDownloads;
}
