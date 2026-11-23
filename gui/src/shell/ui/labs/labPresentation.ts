export function labLoadErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : "unknown error";
  return `Failed to load labs: ${detail}`;
}

export function imageReadout(ref: string): string {
  if (!ref) return "—";
  const short = ref.replace(/^docker\.io\/library\//, "").replace(/^docker\.io\//, "");
  const at = short.indexOf("@sha256:");
  return at === -1 ? short : `${short.slice(0, at)}@${short.slice(at + 8, at + 20)}…`;
}

export function placementReadout(location?: string, image?: string): string {
  const shown = image ? imageReadout(image) : "";
  if (location && shown) return `${shown} @ ${location}`;
  return shown || location || "Unassigned bench";
}
