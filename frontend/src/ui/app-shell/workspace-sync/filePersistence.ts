import { planWorkspaceFilePersistence } from "../../../application/workspace/workspaceFileMutationPlanning";
import type { ReeClient } from "../../../data/ree/client";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "../workflow-runs/types";

interface CreateReeFilePersistenceArgs {
  reeClient: ReeClient<FileTreeNode>;
  reeId: string;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
}

export function createReeFilePersistence({
  reeClient,
  reeId,
  refreshWorkspaceFiles,
  showToast,
}: CreateReeFilePersistenceArgs) {
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
