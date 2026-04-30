export interface WorkspaceShellClock {
  nowIso(): string;
  nowMillis(): number;
}

export interface WorkspaceShellRandom {
  hex(length: number): string;
  int(minInclusive: number, maxInclusive: number): number;
}

export interface WorkspaceShellBrowserDownloads {
  downloadBlob(bytes: BlobPart, options: { fileName: string; mimeType: string }): void;
}

export interface WorkspaceShellRuntimePorts {
  clock: WorkspaceShellClock;
  random: WorkspaceShellRandom;
  sleep(ms: number): Promise<void>;
  browserDownloads: WorkspaceShellBrowserDownloads;
}
