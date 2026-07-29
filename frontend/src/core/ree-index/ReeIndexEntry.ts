// A sealed REE as the index records it, plus wherever it has since been
// deposited. Pure domain shape; the data layer maps the API wire shape onto it.
//
// The identity here is the seal digest, never a workspace id: the same REE can
// exist on several nodes, and only its content identifies it across them. An
// entry can outlive the workbench it was authored in — that is the reason the
// index exists — so nothing here assumes a live REE to navigate to.

/** The archives the backend knows how to record a binding for. */
export type ArchiveProvider = "software_heritage" | "zenodo" | "dataverse";

/**
 * One claim that an archive's deposit holds this REE.
 *
 * A claim about a *deposit event*, not a property of the REE: the same REE can
 * be deposited to several archives and re-deposited as new versions, so an
 * entry carries a list of these rather than one identifier.
 */
export interface ArchiveBinding {
  archive: ArchiveProvider;
  /** The identifier the archive issued, in its own namespace. */
  identifier: string;
  recordUrl: string;
  /** Stable across versions where the archive has such a notion; else "". */
  conceptIdentifier: string;
  version: string;
  /** ISO 8601, or "" when the binding was recorded unsigned. */
  signedAt: string;
}

export interface ReeIndexEntry {
  /** Content identity of the sealed REE, e.g. "sha256:…". The primary key. */
  subjectDigest: string;
  name: string;
  /** ISO 8601 timestamp of when the REE was sealed. */
  sealedAt: string;
  description: string;
  keywords: string[];
  /** The manifest generation this REE was sealed with. */
  reeVersion: string;
  archiveBindings: ArchiveBinding[];
}

// A Map rather than an object literal because the keys are the wire's
// snake_case provider names, which are not this codebase's to rename.
const ARCHIVE_LABELS = new Map<ArchiveProvider, string>([
  ["software_heritage", "Software Heritage"],
  ["zenodo", "Zenodo"],
  ["dataverse", "Dataverse"],
]);

/** Display name for an archive, falling back to the raw key. Pure. */
export function archiveLabel(archive: ArchiveProvider): string {
  return ARCHIVE_LABELS.get(archive) ?? archive;
}

/**
 * Whether any archive has issued an identifier for this REE.
 *
 * Deposit is a predicate over the bindings, not a separate state: an entry
 * exists from the moment the REE is sealed, and depositing only appends to it.
 * An entry with none is a local seal — real here, but not yet citable anywhere
 * else.
 */
export function isDeposited(entry: ReeIndexEntry): boolean {
  return entry.archiveBindings.length > 0;
}

/**
 * The binding to lead with when showing one, or undefined for a local seal.
 *
 * Prefers a citable DOI over an intrinsic identifier: Software Heritage's SWHID
 * says the source exists somewhere, while Zenodo and Dataverse issue something
 * a paper can actually cite. Among equals, first recorded wins.
 */
export function primaryBinding(entry: ReeIndexEntry): ArchiveBinding | undefined {
  return (
    entry.archiveBindings.find((binding) => binding.archive !== "software_heritage") ??
    entry.archiveBindings[0]
  );
}

/** Short, copyable form of the digest: "sha256:abcd1234" → "abcd1234". Pure. */
export function shortDigest(subjectDigest: string): string {
  const [, hex = subjectDigest] = subjectDigest.split(":");
  return hex.slice(0, 12);
}

/**
 * Stable display order: newest seal first, digest breaking ties.
 *
 * The digest tiebreak matters beyond determinism — two entries sealed in the
 * same second must not swap places between renders, and `sealedAt` alone is not
 * unique. Pure; returns a new array.
 */
export function sortReeIndexEntries(entries: readonly ReeIndexEntry[]): ReeIndexEntry[] {
  return [...entries].sort(
    (a, b) =>
      b.sealedAt.localeCompare(a.sealedAt) || a.subjectDigest.localeCompare(b.subjectDigest),
  );
}
