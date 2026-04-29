import type React from "react";
import { useRef } from "react";
import { useWorkspaceRuntime } from "../../../app/WorkspaceRuntime";
import { planSealCommands } from "../../../application/explorer/sealCommands";
import { createServiceRunHandlers } from "../../../application/explorer/serviceRunCommands";
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
} from "../../../types";
import { executeServiceRunCommands } from "./workflow/commandExecutors";
import { createDownloadActions } from "./workflow/downloadActions";
import { createWorkspaceFilePersistence } from "./workflow/filePersistence";
import { executeServiceRunAction } from "./workflow/serviceRuns";
import { createSourceActions, resetWorkflowOnSourceChange } from "./workflow/sourceLifecycle";
import { useWorkspaceDraftSync } from "./workflow/useWorkspaceDraftSync";

interface UseExplorerWorkflowArgs {
  dispatch: React.Dispatch<AppAction>;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
}

export function useExplorerWorkflow({
  dispatch,
  ree,
  level,
  virtualFiles,
  serviceParams,
}: UseExplorerWorkflowArgs) {
  const { createWorkspaceService, ports, workspaceId, workspaceServiceMode } =
    useWorkspaceRuntime();
  const activeRunIdsRef = useRef<Record<string, string>>({});
  const showToast = (msg: string, type: ToastState["type"] = "info") =>
    dispatch(explorerActions.setToast({ message: msg, type }));

  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    resetWorkflowOnSourceChange(dispatch, showToast, options);
  };

  const workspaceService = createWorkspaceService({
    ree,
    virtualFiles,
    serviceParams,
    dispatch,
    executeServiceRun,
  });

  const { buildReePatch, refreshWorkspaceFiles } = useWorkspaceDraftSync({
    ree,
    workspaceService,
    workspaceId,
    workspaceServiceMode,
    hydrateWorkspace: (workspace) => dispatch(explorerActions.hydrateWorkspace(workspace)),
  });

  const { persistWorkspaceFile } = createWorkspaceFilePersistence({
    workspaceService,
    workspaceId,
    refreshWorkspaceFiles,
    showToast,
  });

  const serviceRunHandlers = createServiceRunHandlers({
    ree,
    virtualFiles,
    workspaceServiceMode,
    clock: ports.clock,
  });

  async function executeServiceRun(key: string, params: GenericServiceParams = {}) {
    return executeServiceRunAction({
      key,
      params,
      ree,
      level,
      virtualFiles,
      dispatch,
      persistWorkspaceFile: (path: string, content: string) => {
        void persistWorkspaceFile(undefined, path, content);
      },
      showToast,
      serviceRunHandlers,
      workspaceService,
      workspaceId,
      ports,
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
      workspaceId,
      dispatch,
      onSourceChange: handleSourceChange,
      showToast,
      clock: ports.clock,
      sleep: ports.sleep,
      onRunStarted: (actionKey, runId) => {
        activeRunIdsRef.current[actionKey] = runId;
      },
      onRunFinished: (actionKey) => {
        delete activeRunIdsRef.current[actionKey];
      },
    });

  const handleSeal = () => {
    executeServiceRunCommands(
      planSealCommands({
        sealedAt: ports.clock.nowIso(),
        sealHash: `sha256:${ports.random.hex(64)}`,
      }),
      {
        dispatch,
        persistWorkspaceFile: () => {},
        showToast,
      },
    );
  };

  const { downloadWorkspaceFile, handleDownloadRee } = createDownloadActions({
    workspaceService,
    workspaceId,
    ports,
    getReeName: () => ree.name || "",
    buildReePatch,
    showToast,
  });

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
      await workspaceService.cancelWorkflowRun(workspaceId, runId);
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
