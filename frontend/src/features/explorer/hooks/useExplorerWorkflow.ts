import type React from "react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useWorkspaceRuntime } from "../../../app/WorkspaceRuntime";
import { planSealCommands } from "../../../application/explorer/sealCommands";
import { createServiceRunHandlers } from "../../../application/explorer/serviceRunCommands";
import { createExplorerWorkflowSession } from "../../../application/explorer/workflowSession";
import type { AppAction } from "../../../context";
import { explorerActions } from "../../../context";
import type { WorkspaceServiceLogEntry } from "../../../services/workspaceService";
import type {
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ReeFile,
  ServiceParams,
  WorkflowServiceRunParams,
} from "../../../types";
import { executeServiceRunCommands } from "./workflow/commandExecutors";
import { createDownloadActions } from "./workflow/downloadActions";
import { createWorkspaceFilePersistence } from "./workflow/filePersistence";
import { createServiceRunAdapter } from "./workflow/serviceRunAdapter";
import { createSourceAdapter } from "./workflow/sourceAdapter";
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

  const serviceRunAdapter = createServiceRunAdapter({
    ree,
    level,
    virtualFiles,
    dispatch,
    persistWorkspaceFile: (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    persistWorkflowParams: (key, params) => {
      dispatch(
        explorerActions.setServiceParams((prev) =>
          workflowSession.mergeWorkflowParams(
            prev,
            key,
            params as WorkflowServiceRunParams<typeof key>,
          ),
        ),
      );
    },
    showToast,
    serviceRunHandlers,
    workspaceService,
    workspaceId,
    ports,
    refreshWorkspace,
    workflowSession,
  });

  const sourceAdapter = createSourceAdapter({
    ree,
    workspaceService,
    workspaceId,
    dispatch,
    refreshWorkspaceFiles,
    showToast,
    clock: ports.clock,
    sleep: ports.sleep,
    onRunStarted: workflowSession.noteRunStarted,
    onRunFinished: workflowSession.noteRunFinished,
  });

  useEffect(() => {
    executeServiceRunRef.current = serviceRunAdapter.executeServiceRun;
  });

  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    sourceAdapter;

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

  return {
    handleSeal,
    handleDownloadRee,
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
    downloadWorkspaceFile,
    persistWorkspaceFile,
    runAction: serviceRunAdapter.runAction,
    runWorkflowAction: serviceRunAdapter.runWorkflowAction,
    cancelWorkflowAction: serviceRunAdapter.cancelWorkflowAction,
  };
}
