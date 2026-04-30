import type { WorkspaceBackendGateway } from "../../../application/ports/WorkspaceBackendGateway";
import { planWorkspaceFilePersistence } from "../../../application/workspace/workspaceFileMutationPlanning";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "./types";

interface CreateWorkspaceFilePersistenceArgs {
  workspaceService: WorkspaceBackendGateway<FileTreeNode>;
  workspaceId: string;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
}

export function createWorkspaceFilePersistence({
  workspaceService,
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
      if (plan.shouldDeletePrevious && workspaceService.deleteFile) {
        await workspaceService.deleteFile(workspaceId, plan.normalizedPreviousPath || "");
      }
      await workspaceService.updateFile(workspaceId, plan.normalizedPath, content);
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
