import type { ReeId } from "@core/ree/ReeId";
import {
  planReeArchiveDownload,
  planWorkspaceFileDownload,
} from "@core/workspace/workspaceFileMutationPlanning";
import { appShellPorts } from "@shell/app/bootstrap/appShellPorts";
import { useReeClient } from "@shell/data/ree/client";
import type { ShowToast } from "../types";

interface UseReeDownloadsArgs {
  getReeName: () => string;
  showToast: ShowToast;
  reeId: ReeId;
}

export function useReeDownloads({ getReeName, showToast, reeId }: UseReeDownloadsArgs) {
  const reeClient = useReeClient();

  const downloadWorkspaceFile = async (path: string, suggestedName?: string): Promise<void> => {
    try {
      const fileBytes = await reeClient.getFileBytes(reeId, path);
      const plan = planWorkspaceFileDownload(path, suggestedName);
      appShellPorts.browserDownloads.downloadBlob(fileBytes, {
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
        const archiveDownload = await reeClient.getReeArchive(reeId);
        const plan = planReeArchiveDownload(getReeName(), archiveDownload.fileName);
        appShellPorts.browserDownloads.downloadBlob(archiveDownload.bytes, {
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
