import { useRef } from "react";
import type React from "react";
import { isWorkflowServiceKey } from "../../../constants/services";
import type { AppAction } from "../../../context";
import { explorerActions } from "../../../context";
import type { IWorkspaceService } from "../../../services/workspaceService";
import type {
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ServiceParams,
  ToastState,
  WorkflowServiceKey,
  WorkflowServiceRunParams,
  ZipEntry,
} from "../../../types";
import { buildZipBlob } from "../../../utils";
import { createServiceRunHandlers, executeServiceRunAction } from "./workflow/serviceRuns";
import {
  createExplorerWorkspaceService,
  createSourceActions,
  resetWorkflowOnSourceChange,
  WORKSPACE_ID,
} from "./workflow/sourceLifecycle";
import { createRemoteWorkspaceService } from "../../../services/remoteWorkspaceService";

interface UseExplorerWorkflowArgs {
  dispatch: React.Dispatch<AppAction>;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
  currentReeArchiveEntries: ZipEntry[];
}

export function useExplorerWorkflow({
  dispatch,
  ree,
  level,
  virtualFiles,
  serviceParams,
  currentReeArchiveEntries,
}: UseExplorerWorkflowArgs) {
  const showToast = (msg: string, type: ToastState["type"] = "info") =>
    dispatch(explorerActions.setToast({ message: msg, type }));

  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
  const explicitMode = String(env.VITE_WORKSPACE_SERVICE_MODE || "").toLowerCase();
  const workspaceServiceMode = explicitMode || (env.VITE_API_BASE_URL ? "remote" : "mock");
  const remoteWorkspaceServiceRef = useRef<IWorkspaceService<FileTreeNode> | null>(null);
  if (workspaceServiceMode === "remote" && !remoteWorkspaceServiceRef.current) {
    remoteWorkspaceServiceRef.current = createRemoteWorkspaceService({
      baseUrl: env.VITE_API_BASE_URL || "",
    });
  }

  let workspaceService: IWorkspaceService<FileTreeNode>;

  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    resetWorkflowOnSourceChange(dispatch, showToast, options);
  };

  const remoteWorkspaceService = remoteWorkspaceServiceRef.current;
  workspaceService =
    workspaceServiceMode === "remote"
      ? remoteWorkspaceService ||
        (() => {
          throw new Error("Remote workspace service is not initialized");
        })()
      : createExplorerWorkspaceService({
          ree,
          virtualFiles,
          serviceParams,
          dispatch,
          executeServiceRun,
        });

  const refreshWorkspaceFiles = async (): Promise<FileTreeNode[]> => {
    const workspace = await workspaceService.getWorkspace(WORKSPACE_ID);
    dispatch(explorerActions.setVirtualFiles(workspace.files));
    return workspace.files;
  };

  const persistWorkspaceFile = async (
    previousPath: string | undefined,
    path: string,
    content: string,
  ): Promise<void> => {
    try {
      const previousName = (previousPath || "").trim();
      if (previousName && previousName !== path && workspaceService.deleteFile) {
        await workspaceService.deleteFile(WORKSPACE_ID, previousName);
      }
      await workspaceService.updateFile(WORKSPACE_ID, path, content);
      await refreshWorkspaceFiles();
      showToast(`Saved ${path} to workspace`, "success");
    } catch (error) {
      showToast(
        error instanceof Error ? `Failed to save ${path}: ${error.message}` : `Failed to save ${path}`,
        "error",
      );
    }
  };

  const serviceRunHandlers = createServiceRunHandlers({
    ree,
    virtualFiles,
    dispatch,
    persistWorkspaceFile: (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    showToast,
    workspaceServiceMode: workspaceServiceMode === "remote" ? "remote" : "mock",
  });

  async function executeServiceRun(key: string, params: GenericServiceParams = {}) {
    return executeServiceRunAction({
      key,
      params,
      ree,
      level,
      virtualFiles,
      dispatch,
      showToast,
      serviceRunHandlers,
      workspaceService,
      workspaceId: WORKSPACE_ID,
    });
  }

  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    createSourceActions({
      ree,
      workspaceService,
      dispatch,
      onSourceChange: handleSourceChange,
      showToast,
    });

  const handleSeal = () => {
    const sealHash =
      "sha256:" +
      Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
    dispatch(
      explorerActions.setRee((prevRee) => ({
        ...prevRee,
        _sealedAt: new Date().toISOString(),
        _sealHash: sealHash,
      })),
    );
    dispatch(explorerActions.setLocked(true));
    showToast("REE sealed — now read-only", "success");
  };

  const handleDownloadRee = () => {
    const blob = buildZipBlob(currentReeArchiveEntries);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(ree.name || "ree").replace(/[^a-z0-9_-]/gi, "_")}-capsule.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`Downloaded ${ree.name || "ree"}-capsule.zip`, "success");
  };

  const runAction = async (key: string, params: GenericServiceParams = {}) => {
    if (isWorkflowServiceKey(key)) {
      dispatch(
        explorerActions.setServiceParams((prev) => ({
          ...prev,
          [key]: { ...prev[key], ...params },
        })),
      );
    }
    await executeServiceRun(key, params);
  };

  async function runWorkflowAction<K extends WorkflowServiceKey>(
    key: K,
    params: WorkflowServiceRunParams<K>,
  ): Promise<void> {
    await runAction(key, params);
  }

  return {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    persistWorkspaceFile,
    runAction,
    runWorkflowAction,
  };
}
