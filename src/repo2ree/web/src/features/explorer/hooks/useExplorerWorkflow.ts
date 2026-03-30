import type React from "react";
import { isWorkflowServiceKey } from "../../../constants/services";
import type { AppAction } from "../../../context";
import { explorerActions } from "../../../context";
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
  upsertWorkspaceFile,
} from "./workflow/sourceLifecycle";

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

  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    resetWorkflowOnSourceChange(dispatch, showToast, options);
  };

  const persistWorkspaceFile = (path: string, content: string) => {
    dispatch(
      explorerActions.setVirtualFiles((previousFiles) =>
        upsertWorkspaceFile(previousFiles, path, content),
      ),
    );
  };

  const serviceRunHandlers = createServiceRunHandlers({
    ree,
    virtualFiles,
    dispatch,
    persistWorkspaceFile,
    showToast,
  });

  const executeServiceRun = async (key: string, params: GenericServiceParams = {}) => {
    return executeServiceRunAction({
      key,
      params,
      ree,
      level,
      virtualFiles,
      dispatch,
      showToast,
      serviceRunHandlers,
    });
  };

  const workspaceService = createExplorerWorkspaceService({
    ree,
    virtualFiles,
    serviceParams,
    dispatch,
    executeServiceRun,
  });

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
    runAction,
    runWorkflowAction,
  };
}
