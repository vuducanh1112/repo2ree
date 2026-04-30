import type React from "react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { planSealArtifactCommands } from "../../../application/artifact/sealArtifactCommands";
import type { WorkflowRunLogEntry } from "../../../application/ports/WorkspaceGateway";
import type { GenericServiceParams } from "../../../application/workflow/WorkflowStepTypes";
import type { AutomationStepRunParams } from "../../../application/workflow/WorkflowTypes";
import { createWorkflowRunSession } from "../../../application/workflow/workflowRunSession";
import { createWorkflowStepHandlers } from "../../../application/workflow/workflowStepCommands";
import type { WorkspaceEditorAction } from "../../../application/workspace-editor";
import { workspaceEditorActions } from "../../../application/workspace-editor";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useWorkspaceRuntime } from "../../../runtime/browser/BrowserRuntime";
import { executeWorkflowStepCommands } from "./commandExecutors";
import { createDownloadActions } from "./downloadActions";
import { createWorkspaceFilePersistence } from "./filePersistence";
import { createSourceAdapter } from "./sourceAdapter";
import { useWorkspaceDraftSync } from "./useWorkspaceDraftSync";
import { createWorkflowRunGateway } from "./workflowRunGateway";

interface UseWorkspaceWorkflowArgs {
  dispatch: React.Dispatch<WorkspaceEditorAction>;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
}

export function useWorkspaceWorkflowRuns({
  dispatch,
  ree: reeDraft,
  level,
  virtualFiles,
}: UseWorkspaceWorkflowArgs) {
  const { workspaceGateway, ports, workspaceId } = useWorkspaceRuntime();
  const automationSessionRef = useRef(createWorkflowRunSession());
  const automationSession = automationSessionRef.current;
  const executeServiceRunRef = useRef<
    (key: string, params?: GenericServiceParams) => Promise<WorkflowRunLogEntry>
  >(async () => {
    throw new Error("Service run executor is not ready");
  });
  const showToast = (msg: string, type: "info" | "success" | "error" = "info") =>
    dispatch(workspaceEditorActions.setToast({ message: msg, type }));

  const workspaceService = useMemo(() => workspaceGateway, [workspaceGateway]);

  const hydrateWorkspace = useCallback(
    (workspace: { virtualFiles: FileTreeNode[]; workspaceReeFiles: ReeFile[]; ree?: Ree }) =>
      dispatch(workspaceEditorActions.hydrateWorkspace(workspace)),
    [dispatch],
  );

  const { buildReePatch, refreshWorkspace, refreshWorkspaceFiles } = useWorkspaceDraftSync({
    ree: reeDraft,
    workspaceService,
    workspaceId,
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
