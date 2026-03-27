import type React from "react";
import type {
  ActionStates,
  Badges,
  FileTreeNode,
  Ree,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
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
import type { WorkflowSetters } from "./workflow/types";

interface UseExplorerWorkflowArgs {
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
  currentReeArchiveEntries: ZipEntry[];
  setRee: React.Dispatch<React.SetStateAction<Ree>>;
  setLocked: React.Dispatch<React.SetStateAction<boolean>>;
  setActionStates: React.Dispatch<React.SetStateAction<ActionStates>>;
  setBadges: React.Dispatch<React.SetStateAction<Badges>>;
  setTimestamps: React.Dispatch<React.SetStateAction<Timestamps>>;
  setServiceLogs: React.Dispatch<React.SetStateAction<ServiceLogs>>;
  setServiceParams: React.Dispatch<React.SetStateAction<ServiceParams>>;
  setToast: React.Dispatch<React.SetStateAction<ToastState | null>>;
  setVirtualFiles: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  setImmutableSourceSnapshotFiles: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  setImmutableSourceSnapshotArchiveName: React.Dispatch<React.SetStateAction<string>>;
}

export function useExplorerWorkflow({
  ree,
  level,
  virtualFiles,
  serviceParams,
  currentReeArchiveEntries,
  setRee,
  setLocked,
  setActionStates,
  setBadges,
  setTimestamps,
  setServiceLogs,
  setServiceParams,
  setToast,
  setVirtualFiles,
  setImmutableSourceSnapshotFiles,
  setImmutableSourceSnapshotArchiveName,
}: UseExplorerWorkflowArgs) {
  const setters: WorkflowSetters = {
    setRee,
    setLocked,
    setActionStates,
    setBadges,
    setTimestamps,
    setServiceLogs,
    setServiceParams,
    setToast,
    setVirtualFiles,
    setImmutableSourceSnapshotFiles,
    setImmutableSourceSnapshotArchiveName,
  };

  const showToast = (msg: string, type: ToastState["type"] = "info") =>
    setToast({ message: msg, type });

  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    resetWorkflowOnSourceChange(setters, showToast, options);
  };

  const persistWorkspaceFile = (path: string, content: string) => {
    setVirtualFiles((previousFiles) => upsertWorkspaceFile(previousFiles, path, content));
  };

  const serviceRunHandlers = createServiceRunHandlers({
    ree,
    virtualFiles,
    setRee,
    persistWorkspaceFile,
    showToast,
  });

  const executeServiceRun = async (key: string, params: Record<string, unknown> = {}) => {
    return executeServiceRunAction({
      key,
      params,
      ree,
      level,
      virtualFiles,
      setActionStates,
      setServiceLogs,
      setBadges,
      setTimestamps,
      setLocked,
      setRee,
      showToast,
      serviceRunHandlers,
    });
  };

  const workspaceService = createExplorerWorkspaceService({
    ree,
    virtualFiles,
    serviceParams,
    setRee,
    setVirtualFiles,
    setImmutableSourceSnapshotFiles,
    setImmutableSourceSnapshotArchiveName,
    executeServiceRun,
  });

  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    createSourceActions({
      ree,
      workspaceService,
      setActionStates,
      setBadges,
      setTimestamps,
      onSourceChange: handleSourceChange,
      showToast,
    });

  const handleSeal = () => {
    const sealHash =
      "sha256:" +
      Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
    setRee((prevRee) => ({
      ...prevRee,
      _sealedAt: new Date().toISOString(),
      _sealHash: sealHash,
    }));
    setLocked(true);
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

  const runAction = async (key: string, params: Record<string, unknown> = {}) => {
    setServiceParams((prev) => ({ ...prev, [key]: { ...(prev[key] ?? {}), ...params } }));
    await executeServiceRun(key, params);
  };

  return {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    runAction,
  };
}
