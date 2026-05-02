import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { useCallback, useEffect, useRef } from "react";
import type { AppShellAction } from "../../../application/app-shell";
import { appShellActions } from "../../../application/app-shell";
import { planSealArtifactCommands } from "../../../application/artifact/sealArtifactCommands";
import type { WorkflowRunLogEntry } from "../../../application/ports/repositoryTypes";
import type { GenericWorkflowParams } from "../../../application/workflow/WorkflowStepTypes";
import type { AutomationStepRunParams } from "../../../application/workflow/WorkflowTypes";
import { createWorkflowRunSession } from "../../../application/workflow/workflowRunSession";
import { createWorkflowStepHandlers } from "../../../application/workflow/workflowStepCommands";
import type { ReeDraftViewModel } from "../../../domain/ree/ReeSpec";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import { splitReeDraftViewModel } from "../../../domain/ree/reeDraftViewModel";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { useWorkspaceRuntime } from "../../../runtime/browser/BrowserRuntime";
import { createDownloadActions } from "../artifact-actions/downloadActions";
import { createSourceAdapter } from "../source-acquisition/sourceAdapter";
import { createWorkspaceFilePersistence } from "../workspace-sync/filePersistence";
import {
  useCancelWorkflowRunMutation,
  useStartWorkflowRunMutation,
  useWorkflowRunLogsQuery,
  useWorkflowRunQuery,
} from "../workspace-sync/remoteQueries";
import { useReeDraftSync } from "../workspace-sync/useReeDraftSync";
import { executeWorkflowStepCommands } from "./commandExecutors";
import { createWorkflowRunGateway } from "./workflowRunGateway";

interface UseWorkspaceWorkflowArgs {
  dispatch: React.Dispatch<AppShellAction>;
  ree: ReeDraftViewModel;
  level: number;
  workspaceFiles: FileTreeNode[];
}

export function useWorkspaceWorkflowRuns({
  dispatch,
  ree: reeDraft,
  level,
  workspaceFiles,
}: UseWorkspaceWorkflowArgs) {
  const { artifactRepository, ports, workflowRunRepository, workspaceId, workspaceRepository } =
    useWorkspaceRuntime();
  const queryClient = useQueryClient();
  const automationSessionRef = useRef(createWorkflowRunSession());
  const automationSession = automationSessionRef.current;
  const executeWorkflowRunRef = useRef<
    (key: string, params?: GenericWorkflowParams) => Promise<WorkflowRunLogEntry>
  >(async () => {
    throw new Error("Workflow run executor is not ready");
  });
  const showToast = (msg: string, type: "info" | "success" | "error" = "info") =>
    dispatch(appShellActions.setToast({ message: msg, type }));

  const startWorkflowRunMutation = useStartWorkflowRunMutation({
    workflowRunRepository,
    workspaceId,
  });
  const cancelWorkflowRunMutation = useCancelWorkflowRunMutation({
    workflowRunRepository,
    workspaceId,
  });
  const workflowRunServerState = useWorkflowRunQuery({
    workflowRunRepository,
    workspaceId,
    runId: null,
    enabled: false,
  });
  const workflowRunLogsServerState = useWorkflowRunLogsQuery({
    workflowRunRepository,
    workspaceId,
    runId: null,
    enabled: false,
  });
  void workflowRunServerState;
  void workflowRunLogsServerState;

  const hydrateWorkspace = useCallback(
    (workspace: {
      workspaceFiles: FileTreeNode[];
      reeArtifactFiles: ReeFile[];
      ree?: ReeDraftViewModel;
    }) => {
      if (!workspace.ree) {
        dispatch(
          appShellActions.hydrateWorkspace({
            workspaceFiles: workspace.workspaceFiles,
            reeArtifactFiles: workspace.reeArtifactFiles,
          }),
        );
        return;
      }

      const split = splitReeDraftViewModel(workspace.ree);
      dispatch(
        appShellActions.hydrateWorkspace({
          workspaceFiles: workspace.workspaceFiles,
          reeArtifactFiles: workspace.reeArtifactFiles,
          reeSpec: split.reeSpec,
          workspaceSourceState: split.workspaceSourceState,
          artifactStatus: split.artifactStatus,
          evaluationState: split.evaluationState,
        }),
      );
    },
    [dispatch],
  );

  const { buildReePatch, refreshWorkspace, refreshWorkspaceFiles } = useReeDraftSync({
    ree: reeDraft,
    workspaceRepository,
    workspaceId,
    hydrateWorkspace,
  });

  const { persistWorkspaceFile } = createWorkspaceFilePersistence({
    workspaceRepository,
    workspaceId,
    refreshWorkspaceFiles,
    showToast,
  });

  const workflowStepHandlers = createWorkflowStepHandlers({
    ree: reeDraft,
    workspaceFiles,
    clock: ports.clock,
  });

  const workflowRunGateway = createWorkflowRunGateway({
    ree: reeDraft,
    level,
    workspaceFiles,
    dispatch,
    persistWorkspaceFile: (path: string, content: string) => {
      void persistWorkspaceFile(undefined, path, content);
    },
    persistAutomationStepParams: (key, params) => {
      dispatch(
        appShellActions.setWorkflowParams((prev) =>
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
    workflowRunRepository,
    workspaceId,
    queryClient,
    startWorkflowRun: (scriptKey, params) =>
      startWorkflowRunMutation.mutateAsync({ scriptKey, params }),
    cancelWorkflowRun: (runId) => cancelWorkflowRunMutation.mutateAsync({ runId }),
    ports,
    refreshWorkspace,
    runSession: automationSession,
  });

  const sourceAdapter = createSourceAdapter({
    ree: reeDraft,
    workspaceRepository,
    workflowRunRepository,
    workspaceId,
    queryClient,
    dispatch,
    refreshWorkspaceFiles,
    showToast,
    clock: ports.clock,
    sleep: ports.sleep,
    onRunStarted: automationSession.noteRunStarted,
    onRunFinished: automationSession.noteRunFinished,
  });

  useEffect(() => {
    executeWorkflowRunRef.current = workflowRunGateway.executeWorkflowRun;
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
    workspaceRepository,
    artifactRepository,
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
