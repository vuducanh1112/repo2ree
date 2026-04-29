import type React from "react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useWorkspaceRuntime } from "../../../app/WorkspaceRuntime";
import { planSealArtifactCommands } from "../../../application/artifact/sealArtifactCommands";
import { createWorkflowRunSession } from "../../../application/workflow/workflowRunSession";
import { createWorkflowStepHandlers } from "../../../application/workflow/workflowStepCommands";
import type { WorkspaceEditorAction } from "../../../context";
import { workspaceEditorActions } from "../../../context";
import type {
  AutomationStepRunParams,
  FileTreeNode,
  GenericServiceParams,
  Ree,
  ReeFile,
  ServiceParams,
} from "../../../types";
import type { WorkflowRunLogEntry } from "../../../workspace/WorkspaceGateway";
import { executeWorkflowStepCommands } from "../../explorer/hooks/workflow/commandExecutors";
import { createDownloadActions } from "../../explorer/hooks/workflow/downloadActions";
import { createWorkspaceFilePersistence } from "../../explorer/hooks/workflow/filePersistence";
import { createSourceAdapter } from "../../explorer/hooks/workflow/sourceAdapter";
import { useWorkspaceDraftSync } from "../../explorer/hooks/workflow/useWorkspaceDraftSync";
import { createWorkflowRunGateway } from "../../explorer/hooks/workflow/workflowRunGateway";

interface UseExplorerWorkflowArgs {
  dispatch: React.Dispatch<WorkspaceEditorAction>;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
}

export function useWorkspaceWorkflowRuns({
  dispatch,
  ree: reeDraft,
  level,
  virtualFiles,
  serviceParams,
}: UseExplorerWorkflowArgs) {
  const { createWorkspaceService, ports, workspaceId, workspaceServiceMode } =
    useWorkspaceRuntime();
  const automationSessionRef = useRef(createWorkflowRunSession());
  const automationSession = automationSessionRef.current;
  const executeServiceRunRef = useRef<
    (key: string, params?: GenericServiceParams) => Promise<WorkflowRunLogEntry>
  >(async () => {
    throw new Error("Service run executor is not ready");
  });
  const showToast = (msg: string, type: "info" | "success" | "error" = "info") =>
    dispatch(workspaceEditorActions.setToast({ message: msg, type }));

  const executeServiceRunBridge = useCallback(
    (key: string, params?: GenericServiceParams) => executeServiceRunRef.current(key, params),
    [],
  );

  const workspaceService = useMemo(
    () =>
      createWorkspaceService({
        ree: reeDraft,
        virtualFiles,
        serviceParams,
        dispatch,
        executeServiceRun: executeServiceRunBridge,
      }),
    [
      createWorkspaceService,
      dispatch,
      executeServiceRunBridge,
      reeDraft,
      serviceParams,
      virtualFiles,
    ],
  );

  const hydrateWorkspace = useCallback(
    (workspace: { virtualFiles: FileTreeNode[]; workspaceReeFiles: ReeFile[]; ree?: Ree }) =>
      dispatch(workspaceEditorActions.hydrateWorkspace(workspace)),
    [dispatch],
  );

  const { buildReePatch, refreshWorkspace, refreshWorkspaceFiles } = useWorkspaceDraftSync({
    ree: reeDraft,
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

  const workflowStepHandlers = createWorkflowStepHandlers({
    ree: reeDraft,
    virtualFiles,
    workspaceServiceMode,
    clock: ports.clock,
  });

  const workflowRunGateway = createWorkflowRunGateway({
    ree: reeDraft,
    level,
    virtualFiles,
    dispatch,
    persistWorkspaceFile: (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    persistAutomationStepParams: (key, params) => {
      dispatch(
        workspaceEditorActions.setServiceParams((prev) =>
          automationSession.mergeAutomationStepParams(
            prev,
            key,
            params as AutomationStepRunParams<typeof key>,
          ),
        ),
      );
    },
    showToast,
    workflowStepHandlers,
    workspaceService,
    workspaceId,
    ports,
    refreshWorkspace,
    runSession: automationSession,
  });

  const sourceAdapter = createSourceAdapter({
    ree: reeDraft,
    workspaceService,
    workspaceId,
    dispatch,
    refreshWorkspaceFiles,
    showToast,
    clock: ports.clock,
    sleep: ports.sleep,
    onRunStarted: automationSession.noteRunStarted,
    onRunFinished: automationSession.noteRunFinished,
  });

  useEffect(() => {
    executeServiceRunRef.current = workflowRunGateway.executeServiceRun;
  });

  const { handleDownloadSourceFiles, handleWorkspaceUpload, handleRemoveWorkspaceSource } =
    sourceAdapter;

  const handleSeal = () => {
    executeWorkflowStepCommands(
      planSealArtifactCommands({
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
    getReeName: () => reeDraft.name || "",
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
    runWorkflowStep: workflowRunGateway.runWorkflowStep,
    runAutomationStep: workflowRunGateway.runAutomationStep,
    cancelAutomationStep: workflowRunGateway.cancelAutomationStep,
  };
}
