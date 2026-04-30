import type { WorkspaceShellRuntimePorts } from "../../application/workspace-shell/WorkspaceShellPorts";

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

export function createBrowserRuntimePorts(): WorkspaceShellRuntimePorts {
  return {
    clock: {
      nowIso: () => new Date().toISOString(),
      nowMillis: () => Date.now(),
    },
    random: {
      hex: (length: number) =>
        Array.from(
          { length },
          () => HEX_ALPHABET[Math.floor(Math.random() * HEX_ALPHABET.length)],
        ).join(""),
      int: (minInclusive: number, maxInclusive: number) =>
        Math.floor(Math.random() * (maxInclusive - minInclusive + 1)) + minInclusive,
    },
    sleep: (ms: number) => new Promise((resolve) => setTimeout(resolve, ms)),
    browserDownloads: { downloadBlob },
  };
}
