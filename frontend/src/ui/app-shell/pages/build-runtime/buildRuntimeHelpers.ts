function formatByteSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function deriveRuntimeFileSize(
  runtimeFile: { size?: number; content?: string } | null,
): string | null {
  if (!runtimeFile) return null;
  if (typeof runtimeFile.size === "number" && runtimeFile.size > 0) {
    return formatByteSize(runtimeFile.size);
  }
  const sizeMatch = (runtimeFile.content || "").match(/Size:\s*(~?[\d.]+ ?[KMGT]?B)/i);
  if (sizeMatch) {
    return sizeMatch[1];
  }
  const bytes = new TextEncoder().encode(runtimeFile.content || "").length;
  return formatByteSize(bytes);
}
