export function normalizeWorkspacePath(path: string): string {
  return (path || "").replace(/^\/+/, "").trim();
}

export function archiveWorkspacePath(path: string): string {
  return normalizeWorkspacePath(path).replace(/\.\.+/g, "_");
}

export function normalizeSnapshotArchiveName(rawName: string): string {
  const trimmed = (rawName || "").trim();
  if (!trimmed) return "source.tar.gz";
  if (/\.tar\.gz$/i.test(trimmed)) return trimmed;
  if (/\.tgz$/i.test(trimmed)) return trimmed.replace(/\.tgz$/i, ".tar.gz");
  const stem = trimmed.replace(/\.(zip|tar|tar\.bz2|tar\.xz|tar\.zst|jar)$/i, "");
  return `${stem || "source"}.tar.gz`;
}

export function findTreeFileBySelectedPath(
  files: Array<{ path: string; content: string }>,
  selectedPath: string,
): { path: string; content: string } | null {
  const normalized = normalizeWorkspacePath(selectedPath);
  if (!normalized) return null;
  const exact = files.find((f) => normalizeWorkspacePath(f.path) === normalized);
  if (exact) return exact;
  const selectedBase = normalized.split("/").pop();
  if (!selectedBase) return null;
  return (
    files.find((f) => normalizeWorkspacePath(f.path).split("/").pop() === selectedBase) || null
  );
}
