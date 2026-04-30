import type { ArtifactRepository } from "../../../application/ports/ArtifactRepository";
import type { WorkspaceRepository } from "../../../application/ports/WorkspaceRepository";
import {
  planReeArchiveDownload,
  planWorkspaceFileDownload,
} from "../../../application/workspace/workspaceFileMutationPlanning";
import type { WorkspaceEditorRuntimePorts } from "../../../application/workspace-editor/WorkspaceEditorPorts";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "./types";

interface CreateDownloadActionsArgs {
  workspaceRepository: WorkspaceRepository<FileTreeNode>;
  artifactRepository: ArtifactRepository;
  workspaceId: string;
  ports: WorkspaceEditorRuntimePorts;
  getReeName: () => string;
  buildReePatch: () => Record<string, unknown>;
  showToast: ShowToast;
}

export function createDownloadActions({
  workspaceRepository,
  artifactRepository,
  workspaceId,
  ports,
  getReeName,
  buildReePatch,
  showToast,
}: CreateDownloadActionsArgs) {
  const downloadWorkspaceFile = async (path: string, suggestedName?: string): Promise<void> => {
    try {
      const fileBytes = await workspaceRepository.getFileBytes(workspaceId, path);
      const plan = planWorkspaceFileDownload(path, suggestedName);
      ports.browserDownloads.downloadBlob(fileBytes, {
        fileName: plan.downloadName,
        mimeType: "application/octet-stream",
      });
      showToast(plan.successMessage, "success");
    } catch (error) {
      showToast(
        error instanceof Error
          ? `Failed to download ${path}: ${error.message}`
          : `Failed to download ${path}`,
        "error",
      );
    }
  };

  const handleDownloadRee = () => {
    const runDownload = async () => {
      try {
        await workspaceRepository.updateReeDraft(workspaceId, buildReePatch());
        const archiveDownload = await artifactRepository.getReeArchive(workspaceId);
        const plan = planReeArchiveDownload(getReeName(), archiveDownload.fileName);
        ports.browserDownloads.downloadBlob(archiveDownload.bytes, {
          fileName: plan.archiveFileName,
          mimeType: "application/zip",
        });
        showToast(plan.successMessage, "success");
      } catch (error) {
        showToast(
          error instanceof Error
            ? `Backend archive download failed: ${error.message}`
            : "Backend archive download failed",
          "error",
        );
      }
    };

    void runDownload();
  };

  return {
    downloadWorkspaceFile,
    handleDownloadRee,
  };
}
