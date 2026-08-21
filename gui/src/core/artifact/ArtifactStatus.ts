export interface ArtifactStatus {
  runtimeIncluded?: boolean;
  sealedAt?: string;
  sealHash?: string;
}

/**
 * A REE is sealed once the backend has stamped both a seal time and a content
 * hash into the session. This is the single source of truth for sealed-ness;
 * the shell's read-only UI lock derives from it during workspace hydration.
 */
export function isSealed(status: ArtifactStatus): boolean {
  return Boolean(status.sealedAt && status.sealHash);
}

/**
 * Sealing is terminal and irreversible on the backend, so a server hydration
 * that arrives without seal stamps can only be a stale read (e.g. a workspace
 * GET issued before the seal but resolving after it). Keep the sealed state in
 * that case so a late refresh cannot revert a sealed REE to an editable one.
 *
 * Assumes hydrations target the current REE; switching REEs resets state.
 */
export function preserveSeal(prev: ArtifactStatus, next: ArtifactStatus): ArtifactStatus {
  return isSealed(prev) && !isSealed(next) ? prev : next;
}
