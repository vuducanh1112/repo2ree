import type React from "react";
import { useCallback, useEffect, useRef } from "react";
import { isWorkflowServiceKey } from "../../../constants/services";
import type { AppAction } from "../../../context";
import { explorerActions } from "../../../context";
import { createRemoteWorkspaceService } from "../../../services/remoteWorkspaceService";
import type { IWorkspaceService } from "../../../services/workspaceService";
import type {
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ServiceParams,
  ToastState,
  WorkflowServiceKey,
  WorkflowServiceRunParams,
} from "../../../types";
import { createServiceRunHandlers, executeServiceRunAction } from "./workflow/serviceRuns";
import {
  createExplorerWorkspaceService,
  createSourceActions,
  resetWorkflowOnSourceChange,
  WORKSPACE_ID,
} from "./workflow/sourceLifecycle";

interface UseExplorerWorkflowArgs {
  dispatch: React.Dispatch<AppAction>;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
}

function toReePatch(ree: Ree) {
  return {
    name: ree.name || "",
    origin_url: ree.origin_url || "",
    source_type: ree.source_type || "",
    runtime: ree.runtime || "",
    build_runtime_script: ree.build_runtime_script || "",
    activation_script: ree.activation_script || "",
    sbom: ree.sbom || "",
    swhid: ree.swhid || "",
    zenodo_doi: ree.zenodo_doi || "",
    dataverse_doi: ree.dataverse_doi || "",
    repro_level: ree.repro_level || "",
    detected_dependencies: ree.detected_dependencies || "",
    hardware_description: ree.hardware_description || {},
    _sealedAt: ree._sealedAt || "",
    _sealHash: ree._sealHash || "",
    _evalLevel: ree._evalLevel ?? 0,
    _sourceIncluded: !!ree._sourceIncluded,
    _sourceAvailable: !!ree._sourceAvailable,
    _sourceAcquiredBy: ree._sourceAcquiredBy || "",
    _uploadedArchive: ree._uploadedArchive || "",
    _sourceSnapshotArchive: ree._sourceSnapshotArchive || "",
    _sourceSnapshotCapturedAt: ree._sourceSnapshotCapturedAt || "",
    _runtimeIncluded: !!ree._runtimeIncluded,
    _downloadableFiles: ree._downloadableFiles || [],
  };
}

export function useExplorerWorkflow({
  dispatch,
  ree,
  level,
  virtualFiles,
  serviceParams,
}: UseExplorerWorkflowArgs) {
  const activeRunIdsRef = useRef<Record<string, string>>({});
  const lastSyncedReeRef = useRef<string>("");
  const latestLocalPatchKeyRef = useRef<string>("");
  const isSyncingReeRef = useRef<boolean>(false);
  const hasHydratedRemoteReeRef = useRef<boolean>(false);
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = (msg: string, type: ToastState["type"] = "info") =>
    dispatch(explorerActions.setToast({ message: msg, type }));

  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
  const explicitMode = String(env.VITE_WORKSPACE_SERVICE_MODE || "").toLowerCase();
  const workspaceServiceMode = explicitMode || (env.VITE_API_BASE_URL ? "remote" : "mock");
  const reeIdFromQuery =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("reeId") || undefined
      : undefined;
  const remoteWorkspaceServiceRef = useRef<IWorkspaceService<FileTreeNode> | null>(null);
  if (workspaceServiceMode === "remote" && !remoteWorkspaceServiceRef.current) {
    remoteWorkspaceServiceRef.current = createRemoteWorkspaceService({
      baseUrl: env.VITE_API_BASE_URL || "",
      initialWorkspaceId: reeIdFromQuery,
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

  const refreshWorkspaceFiles = useCallback(
    async (options: { forceReeHydration?: boolean } = {}): Promise<FileTreeNode[]> => {
      const { forceReeHydration = false } = options;
      const workspace = await workspaceService.getWorkspace(WORKSPACE_ID);
      dispatch(explorerActions.setVirtualFiles(workspace.files));
      dispatch(explorerActions.setWorkspaceReeFiles(workspace.reeFiles || []));
      if (workspace.ree) {
        const hasUnsyncedLocalChanges = latestLocalPatchKeyRef.current !== lastSyncedReeRef.current;
        const hasPendingLocalSync =
          hasUnsyncedLocalChanges || !!syncTimerRef.current || isSyncingReeRef.current;
        const shouldHydrateRee =
          forceReeHydration || !hasHydratedRemoteReeRef.current || !hasPendingLocalSync;
        if (shouldHydrateRee) {
          dispatch(explorerActions.setRee(workspace.ree));
          const hydratedPatchKey = JSON.stringify(toReePatch(workspace.ree));
          lastSyncedReeRef.current = hydratedPatchKey;
          latestLocalPatchKeyRef.current = hydratedPatchKey;
          hasHydratedRemoteReeRef.current = true;
        }
      }
      return workspace.files;
    },
    [dispatch, workspaceService],
  );

  const buildReePatch = useCallback(() => toReePatch(ree), [ree]);

  useEffect(() => {
    latestLocalPatchKeyRef.current = JSON.stringify(buildReePatch());
  }, [buildReePatch]);

  useEffect(() => {
    if (workspaceServiceMode !== "remote") {
      return;
    }
    void refreshWorkspaceFiles({ forceReeHydration: true });
  }, [workspaceServiceMode, refreshWorkspaceFiles]);

  useEffect(() => {
    if (workspaceServiceMode !== "remote" || !workspaceService.updateReeDraft) {
      return;
    }
    const patch = buildReePatch();
    const patchKey = JSON.stringify(patch);
    if (patchKey === lastSyncedReeRef.current) {
      return;
    }
    if (syncTimerRef.current) {
      clearTimeout(syncTimerRef.current);
      syncTimerRef.current = null;
    }
    syncTimerRef.current = setTimeout(() => {
      void (async () => {
        isSyncingReeRef.current = true;
        try {
          await workspaceService.updateReeDraft?.(WORKSPACE_ID, patch);
          lastSyncedReeRef.current = patchKey;
          await refreshWorkspaceFiles();
        } catch {
          // Keep local metadata editable; backend sync can be retried on next change.
        } finally {
          isSyncingReeRef.current = false;
        }
      })();
    }, 300);

    return () => {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
      }
    };
  }, [workspaceServiceMode, workspaceService, buildReePatch, refreshWorkspaceFiles]);

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
        error instanceof Error
          ? `Failed to save ${path}: ${error.message}`
          : `Failed to save ${path}`,
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
      onRunStarted: (actionKey, runId) => {
        activeRunIdsRef.current[actionKey] = runId;
      },
      onRunFinished: (actionKey) => {
        delete activeRunIdsRef.current[actionKey];
      },
    });
  }

  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    createSourceActions({
      ree,
      workspaceService,
      dispatch,
      onSourceChange: handleSourceChange,
      showToast,
      onRunStarted: (actionKey, runId) => {
        activeRunIdsRef.current[actionKey] = runId;
      },
      onRunFinished: (actionKey) => {
        delete activeRunIdsRef.current[actionKey];
      },
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

  const downloadWorkspaceFile = async (path: string, suggestedName?: string): Promise<void> => {
    try {
      if (!workspaceService.getFileBytes) {
        throw new Error("Workspace file download is not supported by this service");
      }
      const fileBytes = await workspaceService.getFileBytes(WORKSPACE_ID, path);
      const blob = new Blob([fileBytes], { type: "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = (suggestedName || path.split("/").pop() || "workspace-file").replace(/\\/g, "_");
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(`Downloaded ${a.download}`, "success");
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
      const fallbackReeName = (ree.name || "").trim().replace(/[^A-Za-z0-9._-]+/g, "_") || "ree";
      const fallbackArchiveName = `${fallbackReeName}.zip`;

      if (!workspaceService.getReeArchive) {
        showToast("REE archive download requires backend workspace service", "error");
        return;
      }

      try {
        if (workspaceService.updateReeDraft) {
          await workspaceService.updateReeDraft(WORKSPACE_ID, buildReePatch());
        }
        const archiveDownload = await workspaceService.getReeArchive(WORKSPACE_ID);
        const archiveFileName = archiveDownload.fileName || fallbackArchiveName;
        const blob = new Blob([archiveDownload.bytes], { type: "application/zip" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        if (archiveFileName) {
          a.download = archiveFileName;
        }
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(
          archiveFileName ? `Downloaded ${archiveFileName}` : "Downloaded archive",
          "success",
        );
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

  const cancelWorkflowAction = async (key: string) => {
    const runId = activeRunIdsRef.current[key];
    if (!runId || !workspaceService.cancelWorkflowRun) {
      return;
    }
    try {
      await workspaceService.cancelWorkflowRun(WORKSPACE_ID, runId);
      showToast(`Cancel requested for ${key}`, "info");
    } catch (error) {
      showToast(
        error instanceof Error
          ? `Failed to cancel ${key}: ${error.message}`
          : `Failed to cancel ${key}`,
        "error",
      );
    }
  };

  return {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    downloadWorkspaceFile,
    persistWorkspaceFile,
    runAction,
    runWorkflowAction,
    cancelWorkflowAction,
  };
}
