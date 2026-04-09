import type React from "react";
import { useRef } from "react";
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
  ZipEntry,
} from "../../../types";
import { buildZipBlob, REE_SBOM_PATH, resolveRuntimeArchiveEntryPath } from "../../../utils";
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
  const activeRunIdsRef = useRef<Record<string, string>>({});
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
      if (workspaceService.getReeArchive) {
        try {
          if (workspaceService.updateReeDraft) {
            await workspaceService.updateReeDraft(WORKSPACE_ID, {
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
              hardware_description: ree.hardware_description || {},
              _sealedAt: ree._sealedAt || "",
              _sealHash: ree._sealHash || "",
              _evalLevel: ree._evalLevel ?? 0,
              _sourceIncluded: !!ree._sourceIncluded,
              _sourceAvailable: !!ree._sourceAvailable,
              _sourceAcquiredBy: ree._sourceAcquiredBy || "",
              _sourceSnapshotArchive: ree._sourceSnapshotArchive || "",
              _sourceSnapshotCapturedAt: ree._sourceSnapshotCapturedAt || "",
              _runtimeIncluded: !!ree._runtimeIncluded,
            });
          }
          const archiveBytes = await workspaceService.getReeArchive(WORKSPACE_ID);
          const blob = new Blob([archiveBytes], { type: "application/zip" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `${(ree.name || "ree").replace(/[^a-z0-9_-]/gi, "_")}-capsule.zip`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
          showToast(`Downloaded ${ree.name || "ree"}-capsule.zip`, "success");
          return;
        } catch (error) {
          showToast(
            error instanceof Error
              ? `Backend archive download failed: ${error.message}`
              : "Backend archive download failed",
            "error",
          );
          return;
        }
      }

      let fallbackEntries: ZipEntry[] = [...currentReeArchiveEntries];
      if (workspaceService.getFileBytes) {
        if (ree.sbom && ree.sbom !== "__skipped__") {
          try {
            const sbomBytes = await workspaceService.getFileBytes(WORKSPACE_ID, ree.sbom);
            const sbomData = new Uint8Array(sbomBytes);
            fallbackEntries = fallbackEntries.map((entry) =>
              entry.path === REE_SBOM_PATH ? { ...entry, data: sbomData } : entry,
            );
          } catch {
            // Keep fallback entry as-is when raw download is unavailable.
          }
        }

        if (ree._runtimeIncluded && ree.runtime && ree.runtime !== "__skipped__") {
          try {
            const runtimeBytes = await workspaceService.getFileBytes(WORKSPACE_ID, ree.runtime);
            const runtimeData = new Uint8Array(runtimeBytes);
            const runtimeArchivePath = resolveRuntimeArchiveEntryPath(ree.runtime);
            fallbackEntries = fallbackEntries.map((entry) =>
              entry.path === runtimeArchivePath ? { ...entry, data: runtimeData } : entry,
            );
          } catch {
            // Keep fallback entry as-is when raw download is unavailable.
          }
        }
      }

      const blob = buildZipBlob(fallbackEntries);
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
