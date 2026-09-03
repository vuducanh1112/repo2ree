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

// Keyed by the wire's own state names, so a Map rather than an object literal.
const ALLOCATION_STATE_COPY = new Map<string, string>([
  ["requested", "Requested"],
  ["provisioning", "Provisioning"],
  ["waiting_for_workbench", "Waiting for workbench"],
  ["ready", "Ready"],
  ["assigned", "Assigned"],
  ["draining", "Draining"],
  ["released", "Released"],
  ["failed", "Failed"],
  ["lost", "Lost"],
]);

/**
 * How far obtaining this workbench has got. Unknown states are shown verbatim
 * rather than smoothed over: a control plane ahead of this build should read as
 * itself, not as "Ready".
 */
export function allocationStateCopy(state?: string): string {
  if (!state) return "—";
  return ALLOCATION_STATE_COPY.get(state) ?? state;
}
