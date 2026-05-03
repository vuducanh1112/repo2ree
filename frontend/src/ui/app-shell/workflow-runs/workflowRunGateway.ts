import type { QueryClient } from "@tanstack/react-query";
import type React from "react";
import type { AppShellRuntimePorts } from "../../../application/app-shell/AppShellPorts";
import type {
  WorkflowRunLogEntry,
  WorkflowRunRecord,
} from "../../../application/ports/repositoryTypes";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
import type { GenericWorkflowParams } from "../../../application/workflow/WorkflowStepTypes";
import type {
  AutomationStepKey,
  AutomationStepRunParams,
} from "../../../application/workflow/WorkflowTypes";
import { isAutomationStepKey } from "../../../application/workflow/workflowPolicies";
import type { WorkflowStepHandlerMap } from "../../../application/workflow/workflowStepCommands";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { WorkspaceWorkflowDispatch } from "./commandExecutors";
import type { ShowToast } from "./types";
import { executeWorkflowRunAction } from "./workflowRuns";

interface RunSessionPort {
  noteRunStarted: (key: string, runId: string) => void;
  noteRunFinished: (key: string) => void;
  cancelTrackedRun: (args: {
    key: string;
    cancelRun?: (runId: string) => Promise<unknown>;
  }) => Promise<{ ok: boolean; message?: string }>;
}

interface CreateWorkflowRunGatewayArgs {
  ree: ReeViewState;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: React.Dispatch<unknown> | WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  persistAutomationStepParams: (key: AutomationStepKey, params: GenericWorkflowParams) => void;
  showToast: ShowToast;
  workflowStepHandlers: WorkflowStepHandlerMap;
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
  queryClient: QueryClient;
  startWorkflowRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  cancelWorkflowRun?: (runId: string) => Promise<unknown>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: ReeViewState;
  }>;
  runSession: RunSessionPort;
}

export function createWorkflowRunGateway({
  ree,
  level,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  persistAutomationStepParams,
  showToast,
  workflowStepHandlers,
  workflowRunRepository,
  workspaceId,
  queryClient,
  startWorkflowRun,
  cancelWorkflowRun,
  ports,
  refreshWorkspace,
  runSession,
}: CreateWorkflowRunGatewayArgs) {
  const executeWorkflowRun = async (
    key: string,
    params: GenericWorkflowParams = {},
  ): Promise<WorkflowRunLogEntry> =>
    executeWorkflowRunAction({
      key,
      params,
      ree,
      level,
      workspaceFiles,
      dispatch,
      persistWorkspaceFile,
      showToast,
      workflowStepHandlers,
      workflowRunRepository,
      workspaceId,
      queryClient,
      startWorkflowRun,
      ports,
      refreshWorkspace,
      onRunStarted: runSession.noteRunStarted,
      onRunFinished: runSession.noteRunFinished,
    });

  const runWorkflowStep = async (key: string, params: GenericWorkflowParams = {}) => {
    const automationKey = isAutomationStepKey(key) ? key : null;
    if (automationKey) {
      persistAutomationStepParams(automationKey, params);
    }
    await executeWorkflowRun(key, params);
  };

  const runAutomationStep = async <K extends AutomationStepKey>(
    key: K,
    params: AutomationStepRunParams<K>,
  ): Promise<void> => {
    await runWorkflowStep(key, params);
  };

  const cancelAutomationStep = async (key: string) => {
    const result = await runSession.cancelTrackedRun({
      key,
      cancelRun: cancelWorkflowRun,
    });
    if (result.message) {
      showToast(result.message, result.ok ? "info" : "error");
    }
  };

  return {
    executeWorkflowRun,
    runWorkflowStep,
    runAutomationStep,
    cancelAutomationStep,
  };
}
