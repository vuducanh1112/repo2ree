import type { ExplorerRuntimePorts } from "../../../../application/explorer/runtimePorts";
import {
  planReeArchiveDownload,
  planWorkspaceFileDownload,
} from "../../../../application/explorer/workspaceFilePlanning";
import type { IWorkspaceService } from "../../../../services/workspaceService";
import type { FileTreeNode } from "../../../../types";
import type { ShowToast } from "./types";

interface CreateDownloadActionsArgs {
  workspaceService: IWorkspaceService<FileTreeNode>;
  workspaceId: string;
  ports: ExplorerRuntimePorts;
  getReeName: () => string;
  buildReePatch: () => Record<string, unknown>;
  showToast: ShowToast;
}

export function createDownloadActions({
  workspaceService,
  workspaceId,
  ports,
  getReeName,
  buildReePatch,
  showToast,
}: CreateDownloadActionsArgs) {
  const downloadWorkspaceFile = async (path: string, suggestedName?: string): Promise<void> => {
    try {
      if (!workspaceService.getFileBytes) {
        throw new Error("Workspace file download is not supported by this service");
      }
      const fileBytes = await workspaceService.getFileBytes(workspaceId, path);
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
      if (!workspaceService.getReeArchive) {
        showToast("REE archive download requires backend workspace service", "error");
        return;
      }

      try {
        if (workspaceService.updateReeDraft) {
          await workspaceService.updateReeDraft(workspaceId, buildReePatch());
        }
        const archiveDownload = await workspaceService.getReeArchive(workspaceId);
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
