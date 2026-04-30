export interface ArtifactStatus {
  runtimeIncluded?: boolean;
  downloadableFiles?: string[];
  sealedAt?: string;
  sealHash?: string;
}
