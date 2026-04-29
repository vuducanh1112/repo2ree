export interface ExplorerClock {
  nowIso(): string;
  nowMillis(): number;
}

export interface ExplorerRandom {
  hex(length: number): string;
  int(minInclusive: number, maxInclusive: number): number;
}

export interface ExplorerBrowserDownloads {
  downloadBlob(bytes: BlobPart, options: { fileName: string; mimeType: string }): void;
}

export interface ExplorerRuntimePorts {
  clock: ExplorerClock;
  random: ExplorerRandom;
  sleep(ms: number): Promise<void>;
  browserDownloads: ExplorerBrowserDownloads;
}
