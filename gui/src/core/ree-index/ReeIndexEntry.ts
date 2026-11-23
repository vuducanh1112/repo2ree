export type ArchiveProvider = "software_heritage" | "zenodo" | "dataverse";

export interface ArchiveBinding {
  archive: ArchiveProvider;
  identifier: string;
  recordUrl: string;
  conceptIdentifier: string;
  version: string;
  signedAt: string;
}

export interface ReeIndexEntry {
  subjectDigest: string;
  name: string;
  sealedAt: string;
  description: string;
  keywords: string[];
  reeVersion: string;
  archiveBindings: ArchiveBinding[];
}

const ARCHIVE_LABELS = new Map<ArchiveProvider, string>([
  ["software_heritage", "Software Heritage"],
  ["zenodo", "Zenodo"],
  ["dataverse", "Dataverse"],
]);

export function archiveLabel(archive: ArchiveProvider): string {
  return ARCHIVE_LABELS.get(archive) ?? archive;
}

export function isDeposited(entry: ReeIndexEntry): boolean {
  return entry.archiveBindings.length > 0;
}

export function primaryBinding(entry: ReeIndexEntry): ArchiveBinding | undefined {
  return (
    entry.archiveBindings.find((binding) => binding.archive !== "software_heritage") ??
    entry.archiveBindings[0]
  );
}

export function shortDigest(subjectDigest: string): string {
  const [, hex = subjectDigest] = subjectDigest.split(":");
  return hex.slice(0, 12);
}

export function sortReeIndexEntries(entries: readonly ReeIndexEntry[]): ReeIndexEntry[] {
  return [...entries].sort(
    (a, b) =>
      b.sealedAt.localeCompare(a.sealedAt) || a.subjectDigest.localeCompare(b.subjectDigest),
  );
}
