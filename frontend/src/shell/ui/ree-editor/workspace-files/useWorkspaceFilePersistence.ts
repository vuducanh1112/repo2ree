import { useQueryClient } from "@tanstack/react-query";
import type { FileTreeNode } from "../../../../core/workspace/FileTree";
import { planWorkspaceFilePersistence } from "../../../../core/workspace/workspaceFileMutationPlanning";
import { useApiRuntime } from "../../../data/apiRuntime";
import { queryKeys } from "../../../data/queryKeys";
import { useReeClient } from "../../../data/ree/client";
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
  const queryClient = useQueryClient();

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
      await queryClient.invalidateQueries({ queryKey: queryKeys.receipts(reeId) });
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
