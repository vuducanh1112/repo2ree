export interface AppShellClock {
  nowIso(): string;
  nowMillis(): number;
}

export interface AppShellRandom {
  hex(length: number): string;
  int(minInclusive: number, maxInclusive: number): number;
}

export interface AppShellBrowserDownloads {
  downloadBlob(bytes: BlobPart, options: { fileName: string; mimeType: string }): void;
}

export interface AppShellRuntimePorts {
  clock: AppShellClock;
  random: AppShellRandom;
  sleep(ms: number): Promise<void>;
  browserDownloads: AppShellBrowserDownloads;
}
