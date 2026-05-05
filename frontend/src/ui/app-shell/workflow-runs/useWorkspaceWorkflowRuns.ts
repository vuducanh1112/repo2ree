import { useQueryClient } from "@tanstack/react-query";
import type React from "react";
import { useCallback, useEffect, useRef } from "react";
import { appShellPorts } from "../../../app/bootstrap/appShellPorts";
import { planSealArtifactCommands } from "../../../application/artifact/sealArtifactCommands";
import { initialReeAssemblyOperationParams } from "../../../application/ree-assembly/assemblyCatalog";
import { createAssemblyCommandPlanners } from "../../../application/ree-assembly/assemblyCommands";
import { createAssemblyRunSession } from "../../../application/ree-assembly/assemblyRunSession";
import type { ReeEditorViewModel } from "../../../application/ree-editor/reeEditorViewModel";
import { patch } from "../../../application/state/actions";
import type { AppShellAction } from "../../../application/state/types";
import type { GenericWorkflowParams } from "../../../application/workflow/WorkflowStepTypes";
import type { AutomationStepRunParams } from "../../../application/workflow/WorkflowTypes";
import { useApiRuntime } from "../../../data/apiRuntime";
import { useExecutionRunsClient } from "../../../data/execution-runs/client";
import {
  useCancelExecutionRunMutation,
  useStartExecutionRunMutation,
} from "../../../data/execution-runs/mutations";
import { useReeClient } from "../../../data/ree/client";
import type { RawReeDraftSlices } from "../../../domain/ree/mapRawReeDraft";
import type { LogEntry, ReeFile } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { createDownloadActions } from "../artifact-actions/downloadActions";
import { createSourceAdapter } from "../source-acquisition/sourceAdapter";
import { createReeFilePersistence } from "../workspace-sync/filePersistence";
import { useReeDraftSync } from "../workspace-sync/useReeDraftSync";
import { executeWorkflowStepCommands } from "./commandExecutors";
import { createWorkflowRunGateway } from "./workflowRunGateway";

interface UseWorkspaceWorkflowArgs {
  dispatch: React.Dispatch<AppShellAction>;
  ree: ReeEditorViewModel;
  level: number;
  workspaceFiles: FileTreeNode[];
}

export function useWorkspaceWorkflowRuns({
  dispatch,
  ree: reeDraft,
  level,
  workspaceFiles,
}: UseWorkspaceWorkflowArgs) {
  const { reeId } = useApiRuntime();
  const reeClient = useReeClient();
  const workflowRunsClient = useExecutionRunsClient();
  const ports = appShellPorts;
  const queryClient = useQueryClient();
  const automationSessionRef = useRef(createAssemblyRunSession());
  const automationSession = automationSessionRef.current;
  const executeWorkflowRunRef = useRef<
    (key: string, params?: GenericWorkflowParams) => Promise<LogEntry>
  >(async () => {
    throw new Error("Workflow run executor is not ready");
  });
  const showToast = (msg: string, type: "info" | "success" | "error" = "info") =>
    dispatch(patch("uiChrome", { toast: { message: msg, type } }));

  const startWorkflowRunMutation = useStartExecutionRunMutation(reeId);
  const cancelWorkflowRunMutation = useCancelExecutionRunMutation(reeId);

  const hydrateWorkspace = useCallback(
    (workspace: {
      workspaceFiles: FileTreeNode[];
      reeArtifactFiles: ReeFile[];
      ree?: RawReeDraftSlices;
    }) => {
      if (!workspace.ree) {
        // No state to hydrate - workspace files come from React Query
        return;
      }

      dispatch(
        patch("reeDraft", {
          reeSpec: workspace.ree.reeSpec,
        }),
      );
      dispatch(
        patch("reeDraft", {
          workspaceSourceState: workspace.ree.workspaceSourceState,
        }),
      );
      dispatch(
        patch("reeDraft", {
          artifactStatus: workspace.ree.artifactStatus,
        }),
      );
      dispatch(patch("workflowRun", { evaluationState: workspace.ree.evaluationState }));
    },
    [dispatch],
  );

  const { buildReePatch, refreshWorkspace, refreshWorkspaceFiles } = useReeDraftSync({
    ree: reeDraft,
    reeId,
    hydrateWorkspace,
  });

  const { persistWorkspaceFile } = createReeFilePersistence({
    reeClient,
    reeId,
    refreshWorkspaceFiles,
    showToast,
  });

  const workflowStepHandlers = createAssemblyCommandPlanners({
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
        patch("workflowRun", (prev) => ({
          workflowParams: automationSession.mergeAssemblyOperationParams(
            prev.workflowParams ?? initialReeAssemblyOperationParams(),
            key,
            params as AutomationStepRunParams<typeof key>,
          ),
        })),
      );
    },
    showToast,
    workflowStepHandlers,
    workflowRunsClient,
    reeId,
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
    reeClient,
    workflowRunsClient,
    reeId,
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
    reeClient,
    reeId,
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
