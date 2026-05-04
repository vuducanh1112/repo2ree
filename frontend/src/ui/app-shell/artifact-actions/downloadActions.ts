import type { AppShellRuntimePorts } from "../../../application/app-shell/AppShellPorts";
import {
  planReeArchiveDownload,
  planWorkspaceFileDownload,
} from "../../../application/workspace/workspaceFileMutationPlanning";
import type { ReeClient } from "../../../data/ree/client";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "../workflow-runs/types";

interface CreateDownloadActionsArgs {
  reeClient: ReeClient<FileTreeNode>;
  reeId: string;
  ports: AppShellRuntimePorts;
  getReeName: () => string;
  buildReePatch: () => Record<string, unknown>;
  showToast: ShowToast;
}

export function createDownloadActions({
  reeClient,
  reeId,
  ports,
  getReeName,
  buildReePatch,
  showToast,
}: CreateDownloadActionsArgs) {
  const downloadWorkspaceFile = async (path: string, suggestedName?: string): Promise<void> => {
    try {
      const fileBytes = await reeClient.getFileBytes(reeId, path);
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
        await reeClient.updateReeDraft(reeId, buildReePatch());
        const archiveDownload = await reeClient.getReeArchive(reeId);
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
