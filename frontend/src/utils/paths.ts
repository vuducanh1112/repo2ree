export function normalizeSnapshotArchiveName(rawName: string): string {
  const trimmed = (rawName || "").trim();
  if (!trimmed) return "source.tar.gz";
  if (/\.tar\.gz$/i.test(trimmed)) return trimmed;
  if (/\.tgz$/i.test(trimmed)) return trimmed.replace(/\.tgz$/i, ".tar.gz");
  const stem = trimmed.replace(/\.(zip|tar|tar\.bz2|tar\.xz|tar\.zst|jar)$/i, "");
  return `${stem || "source"}.tar.gz`;
}
