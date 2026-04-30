import type { WorkspaceBinaryDownload } from "./repositoryTypes";

export interface ArtifactRepository {
  getReeArchive(id: string): Promise<WorkspaceBinaryDownload>;
}
