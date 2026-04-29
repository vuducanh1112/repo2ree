import type React from "react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useWorkspaceRuntime } from "../../../app/WorkspaceRuntime";
import { planSealCommands } from "../../../application/explorer/sealCommands";
import { createServiceRunHandlers } from "../../../application/explorer/serviceRunCommands";
import { createExplorerWorkflowSession } from "../../../application/explorer/workflowSession";
import { isWorkflowServiceKey } from "../../../constants/services";
import type { AppAction } from "../../../context";
import { explorerActions } from "../../../context";
import type { WorkspaceServiceLogEntry } from "../../../services/workspaceService";
import type {
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ReeFile,
  ServiceParams,
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
  const workflowSessionRef = useRef(createExplorerWorkflowSession());
  const workflowSession = workflowSessionRef.current;
  const executeServiceRunRef = useRef<
    (key: string, params?: GenericServiceParams) => Promise<WorkspaceServiceLogEntry>
  >(async () => {
    throw new Error("Service run executor is not ready");
  });
  const showToast = (msg: string, type: "info" | "success" | "error" = "info") =>
    dispatch(explorerActions.setToast({ message: msg, type }));

  const handleSourceChange = (options: { silent?: boolean } = {}) => {
    resetWorkflowOnSourceChange(dispatch, showToast, options);
  };

  const executeServiceRunBridge = useCallback(
    (key: string, params?: GenericServiceParams) => executeServiceRunRef.current(key, params),
    [],
  );

  const workspaceService = useMemo(
    () =>
      createWorkspaceService({
        ree,
        virtualFiles,
        serviceParams,
        dispatch,
        executeServiceRun: executeServiceRunBridge,
      }),
    [createWorkspaceService, dispatch, executeServiceRunBridge, ree, serviceParams, virtualFiles],
  );

  const hydrateWorkspace = useCallback(
    (workspace: { virtualFiles: FileTreeNode[]; workspaceReeFiles: ReeFile[]; ree?: Ree }) =>
      dispatch(explorerActions.hydrateWorkspace(workspace)),
    [dispatch],
  );

  const { buildReePatch, refreshWorkspace, refreshWorkspaceFiles } = useWorkspaceDraftSync({
    ree,
    workspaceService,
    workspaceId,
    workspaceServiceMode,
    hydrateWorkspace,
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
      refreshWorkspace,
      onRunStarted: workflowSession.noteRunStarted,
      onRunFinished: workflowSession.noteRunFinished,
    });
  }

  useEffect(() => {
    executeServiceRunRef.current = executeServiceRun;
  });

  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    createSourceActions({
      ree,
      workspaceService,
      workspaceId,
      dispatch,
      refreshWorkspaceFiles,
      onSourceChange: handleSourceChange,
      showToast,
      clock: ports.clock,
      sleep: ports.sleep,
      onRunStarted: workflowSession.noteRunStarted,
      onRunFinished: workflowSession.noteRunFinished,
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
        explorerActions.setServiceParams((prev) =>
          workflowSession.mergeWorkflowParams(
            prev,
            key,
            params as WorkflowServiceRunParams<typeof key>,
          ),
        ),
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
    const cancelWorkflowRun = workspaceService.cancelWorkflowRun;
    const cancelRun = cancelWorkflowRun
      ? (runId: string) => cancelWorkflowRun(workspaceId, runId)
      : undefined;
    const result = await workflowSession.cancelTrackedRun({
      key,
      cancelRun,
    });
    if (result.message) {
      showToast(result.message, result.ok ? "info" : "error");
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
