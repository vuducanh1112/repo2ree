export interface ArtifactStatus {
  experimentEnvironmentIncluded?: boolean;
  sealedAt?: string;
  sealHash?: string;
}

export function isSealed(status: ArtifactStatus): boolean {
  return Boolean(status.sealedAt && status.sealHash);
}

export function preserveSeal(prev: ArtifactStatus, next: ArtifactStatus): ArtifactStatus {
  return isSealed(prev) && !isSealed(next) ? prev : next;
}
