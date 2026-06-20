import type { FileTreeNode } from "@core/workspace/FileTree";
import { planWorkspaceFilePersistence } from "@core/workspace/workspaceFileMutationPlanning";
import { useApiRuntime } from "@shell/data/apiRuntime";
import { useReeClient } from "@shell/data/ree/client";
import type { ShowToast } from "../types";

interface UseWorkspaceFilePersistenceArgs {
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
}

export function useWorkspaceFilePersistence({
  refreshWorkspaceFiles,
  showToast,
}: UseWorkspaceFilePersistenceArgs) {
  const { reeId } = useApiRuntime();
  const reeClient = useReeClient();

  const persistWorkspaceFile = async (
    previousPath: string | undefined,
    path: string,
    content: string,
  ): Promise<void> => {
    try {
      const plan = planWorkspaceFilePersistence(previousPath, path);
      if (plan.shouldDeletePrevious) {
        await reeClient.deleteFile(reeId, plan.normalizedPreviousPath || "");
      }
      await reeClient.updateFile(reeId, plan.normalizedPath, content);
      await refreshWorkspaceFiles();
      showToast(plan.successMessage, "success");
    } catch (error) {
      showToast(
        error instanceof Error
          ? `Failed to save ${path}: ${error.message}`
          : `Failed to save ${path}`,
        "error",
      );
    }
  };

  return { persistWorkspaceFile };
}
