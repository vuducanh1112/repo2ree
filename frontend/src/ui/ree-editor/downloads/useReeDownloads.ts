import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
import {
  planReeArchiveDownload,
  planWorkspaceFileDownload,
} from "../../../core/workspace/workspaceFileMutationPlanning";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useReeClient } from "../../../data/ree/client";
import type { ShowToast } from "../types";

interface UseReeDownloadsArgs {
  buildReePatch: () => Record<string, unknown>;
  getReeName: () => string;
  showToast: ShowToast;
}

export function useReeDownloads({ buildReePatch, getReeName, showToast }: UseReeDownloadsArgs) {
  const { reeId } = useApiRuntime();
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
        await reeClient.updateReeDraft(reeId, buildReePatch());
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
