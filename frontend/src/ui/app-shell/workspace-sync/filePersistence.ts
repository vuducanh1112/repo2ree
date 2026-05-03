import { planWorkspaceFilePersistence } from "../../../application/workspace/workspaceFileMutationPlanning";
import type { WorkspaceClient } from "../../../data/ree/client";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "../workflow-runs/types";

interface CreateWorkspaceFilePersistenceArgs {
  workspaceClient: WorkspaceClient<FileTreeNode>;
  workspaceId: string;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
}

export function createWorkspaceFilePersistence({
  workspaceClient,
  workspaceId,
  refreshWorkspaceFiles,
  showToast,
}: CreateWorkspaceFilePersistenceArgs) {
  const persistWorkspaceFile = async (
    previousPath: string | undefined,
    path: string,
    content: string,
  ): Promise<void> => {
    try {
      const plan = planWorkspaceFilePersistence(previousPath, path);
      if (plan.shouldDeletePrevious) {
        await workspaceClient.deleteFile(workspaceId, plan.normalizedPreviousPath || "");
      }
      await workspaceClient.updateFile(workspaceId, plan.normalizedPath, content);
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
