import type { ArtifactRepository } from "../../application/ports/ArtifactRepository";
import type { HttpRepositoryClient } from "./HttpRepositoryClient";

export function createHttpArtifactRepository(
  repositoryClient: HttpRepositoryClient,
): ArtifactRepository {
  return {
    async getReeArchive(id) {
      const workspaceId = await repositoryClient.ensureWorkspaceId(id);
      return repositoryClient.workspaceApi.getReeArchive(workspaceId);
    },
  };
}
