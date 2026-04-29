import type { ExplorerRuntimePorts } from "../application/explorer/runtimePorts";

const HEX_ALPHABET = "0123456789abcdef";

function downloadBlob(bytes: BlobPart, options: { fileName: string; mimeType: string }): void {
  const blob = new Blob([bytes], { type: options.mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = options.fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function createBrowserRuntimePorts(): ExplorerRuntimePorts {
  return {
    clock: {
      nowIso: () => new Date().toISOString(),
      nowMillis: () => Date.now(),
    },
    random: {
      hex: (length) =>
        Array.from(
          { length },
          () => HEX_ALPHABET[Math.floor(Math.random() * HEX_ALPHABET.length)],
        ).join(""),
      int: (minInclusive, maxInclusive) =>
        Math.floor(Math.random() * (maxInclusive - minInclusive + 1)) + minInclusive,
    },
    sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    browserDownloads: { downloadBlob },
  };
}
