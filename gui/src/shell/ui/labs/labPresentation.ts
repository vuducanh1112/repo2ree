export function labLoadErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : "unknown error";
  return `Failed to load labs: ${detail}`;
}

/**
 * Shortens an image ref to something that fits a cell without lying about it:
 * the implicit Docker Hub prefix goes, and a digest is truncated to its first
 * bytes. The tag is always kept — it is the half an author recognises.
 */
export function imageReadout(ref: string): string {
  if (!ref) return "—";
  const short = ref.replace(/^docker\.io\/library\//, "").replace(/^docker\.io\//, "");
  const at = short.indexOf("@sha256:");
  return at === -1 ? short : `${short.slice(0, at)}@${short.slice(at + 8, at + 20)}…`;
}

/**
 * Names where a REE actually runs, for the ambient bench readouts: the image it
 * was built from, and the lab it was built at. The image is shown on purpose —
 * it is the base of everything the REE will claim to reproduce.
 */
export function placementReadout(location?: string, image?: string): string {
  const shown = image ? imageReadout(image) : "";
  if (location && shown) return `${shown} @ ${location}`;
  return shown || location || "Unassigned bench";
}
